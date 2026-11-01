"""M2: selective discourse context (paper Section IV-F).

For each ambiguous word in the current sentence:
  1. Can the sentence itself settle the sense?          -> NO_CONTEXT_REQUIRED
  2. Otherwise score each preceding sentence in a sliding window for relevance
     (sense-cue hits x recency weight) and keep only relevant ones.
       no context given                                  -> CONTEXT_INSUFFICIENT
       context given, none relevant                      -> CONTEXT_IRRELEVANT
       relevant context, one sense clearly wins          -> RELEVANT_CONTEXT_SELECTED
       relevant context, senses too close                -> CONTEXT_AMBIGUOUS

NLLB stays a sentence-level model: selected context is used only to choose a
meaning-explicit wording of the current sentence (see context_rewrites).
Scores are transparent rule scores, not probabilities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.modules.rewrite import Rewrite
from app.modules.sense_inventory import AmbiguousWord, load_inventory
from app.modules.text_utils import cue_matches, match_case, normalize_same_length, tokens

NO_CONTEXT_REQUIRED = "NO_CONTEXT_REQUIRED"
RELEVANT_CONTEXT_SELECTED = "RELEVANT_CONTEXT_SELECTED"
CONTEXT_IRRELEVANT = "CONTEXT_IRRELEVANT"
CONTEXT_INSUFFICIENT = "CONTEXT_INSUFFICIENT"
CONTEXT_AMBIGUOUS = "CONTEXT_AMBIGUOUS"


@dataclass(frozen=True)
class ContextConfig:
    window_size: int = 3  # number of preceding sentences considered
    recency_decay: float = 0.8  # weight = decay ** (distance - 1)
    min_sentence_relevance: float = 0.5  # a context sentence is selected if its weighted cue score >= this
    in_sentence_margin: float = 1.0  # cue-count lead needed to resolve from the sentence alone
    min_sense_support: float = 0.75  # winning sense needs at least this much weighted support
    sense_margin: float = 0.5  # ...and must lead the runner-up by at least this much

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SentenceScore:
    index: int  # position in the provided context list
    distance: int  # 1 = immediately preceding sentence
    text: str
    weight: float
    hits: dict[str, list[str]]  # sense_id -> cues found
    relevance: float
    selected: bool


@dataclass
class WordAnalysis:
    word_id: str
    lemma: str
    matched_text: str
    start: int
    end: int
    state: str
    in_sentence_hits: dict[str, list[str]]
    sentence_scores: list[SentenceScore] = field(default_factory=list)
    sense_support: dict[str, float] = field(default_factory=dict)
    resolved_sense: str | None = None
    resolved_gloss: str | None = None
    replacement: str | None = None  # None when no rewrite is needed
    reason: str = ""


@dataclass
class ContextAnalysis:
    state: str  # summary over all ambiguous words
    words: list[WordAnalysis]
    selected_context: list[str]
    window: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def _hits(word: AmbiguousWord, text: str, exclude: tuple[int, int] | None = None) -> dict[str, list[str]]:
    if exclude:
        text = text[: exclude[0]] + " " + text[exclude[1]:]
    toks = tokens(text)
    joined = " ".join(toks)
    return {s.sense_id: [c for c in s.cues if cue_matches(c, toks, joined)] for s in word.senses}


def _top_two(scores: dict[str, float]) -> tuple[tuple[str, float], float]:
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[0], (ranked[1][1] if len(ranked) > 1 else 0.0)


_STATE_PRIORITY = [RELEVANT_CONTEXT_SELECTED, CONTEXT_AMBIGUOUS, CONTEXT_IRRELEVANT, CONTEXT_INSUFFICIENT, NO_CONTEXT_REQUIRED]


class ContextSelector:
    def __init__(self, words: list[AmbiguousWord] | None = None, config: ContextConfig | None = None):
        self.words = words if words is not None else load_inventory()[1]
        self.config = config or ContextConfig()

    def analyze(self, text: str, source_lang: str, context: list[str] | None = None) -> ContextAnalysis:
        cfg = self.config
        context = [c for c in (context or []) if c.strip()]
        offset = max(0, len(context) - cfg.window_size)
        window = context[offset:]
        norm = normalize_same_length(text)
        results: list[WordAnalysis] = []
        for w in self.words:
            if w.source_language != source_lang:
                continue
            for m in w.regex.finditer(norm):
                results.append(self._analyze_word(w, norm, text, m.start(), m.end(), window, offset))
        results.sort(key=lambda r: r.start)
        if not results:
            state = NO_CONTEXT_REQUIRED
        else:
            state = min((r.state for r in results), key=_STATE_PRIORITY.index)
        selected = sorted({s.index for r in results for s in r.sentence_scores if s.selected})
        return ContextAnalysis(state, results, [context[i] for i in selected], window)

    def _analyze_word(self, w, norm, original, start, end, window, offset) -> WordAnalysis:
        cfg = self.config
        surface = original[start:end]
        in_hits = _hits(w, norm, (start, end))
        wa = WordAnalysis(w.word_id, w.lemma, surface, start, end, "", in_hits)
        in_scores = {k: float(len(v)) for k, v in in_hits.items()}
        (top_sense, top), second = _top_two(in_scores)
        if top >= 1 and top - second >= cfg.in_sentence_margin:
            wa.state, wa.sense_support = NO_CONTEXT_REQUIRED, in_scores
            wa.resolved_sense = top_sense
            wa.reason = f"sentence itself indicates {top_sense} (cues {in_hits[top_sense]})"
            return wa
        if not window:
            wa.state, wa.sense_support = CONTEXT_INSUFFICIENT, in_scores
            wa.reason = "ambiguous in isolation and no preceding context was provided"
            return wa

        support = dict(in_scores)
        for dist, sent in enumerate(reversed(window), start=1):
            weight = round(cfg.recency_decay ** (dist - 1), 4)
            hits = _hits(w, normalize_same_length(sent))
            relevance = round(weight * sum(len(v) for v in hits.values()), 4)
            selected = relevance >= cfg.min_sentence_relevance
            wa.sentence_scores.append(SentenceScore(offset + len(window) - dist, dist, sent, weight,
                                                    {k: v for k, v in hits.items() if v}, relevance, selected))
            if selected:
                for k, v in hits.items():
                    support[k] += weight * len(v)
        wa.sentence_scores.reverse()  # oldest first, as provided
        wa.sense_support = {k: round(v, 4) for k, v in support.items()}

        if not any(s.selected for s in wa.sentence_scores):
            wa.state = CONTEXT_IRRELEVANT
            wa.reason = f"none of the {len(window)} preceding sentence(s) contains cues for any sense of '{w.lemma}'"
            return wa
        (top_sense, top), second = _top_two(wa.sense_support)
        if top >= cfg.min_sense_support and top - second >= cfg.sense_margin:
            sense = next(s for s in w.senses if s.sense_id == top_sense)
            wa.state, wa.resolved_sense, wa.resolved_gloss = RELEVANT_CONTEXT_SELECTED, top_sense, sense.gloss
            rep = sense.replacements.get(surface.lower())
            wa.replacement = match_case(rep, surface) if rep and rep.lower() != surface.lower() else None
            wa.reason = (f"selected context supports {top_sense} ({top:.2f} vs {second:.2f})"
                         + ("" if wa.replacement else "; resolved sense needs no rewrite"))
        else:
            wa.state = CONTEXT_AMBIGUOUS
            wa.reason = f"senses too close: top {top_sense}={top:.2f}, runner-up={second:.2f} (margin {cfg.sense_margin})"
        return wa


def context_rewrites(text: str, words: list[WordAnalysis]) -> list[Rewrite]:
    return [Rewrite("context", w.word_id, w.start, w.end, text[w.start:w.end], w.replacement)
            for w in words if w.state == RELEVANT_CONTEXT_SELECTED and w.replacement]
