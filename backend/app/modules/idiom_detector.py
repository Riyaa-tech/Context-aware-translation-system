"""M1 step 1+2: idiom candidate detection and literal-vs-figurative usage assessment.

The usage score is a transparent RULE SCORE (prior + cue adjustments), not a calibrated
probability. Thresholds live in IdiomConfig and must be tuned on development data only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.modules.idiom_lexicon import IdiomEntry, load_lexicon
from app.modules.text_utils import TOKEN_RE, cue_matches, normalize_same_length, tokens


@dataclass(frozen=True)
class IdiomConfig:
    figurative_cue_weight: float = 0.10
    max_figurative_bonus: float = 0.20
    literal_cue_weight: float = 0.40
    literal_follower_weight: float = 0.50
    figurative_threshold: float = 0.60  # score >= this -> "figurative"
    literal_threshold: float = 0.40  # score <= this -> "literal"; in between -> "uncertain"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class IdiomCandidate:
    idiom_id: str
    expression: str
    matched_text: str
    start: int
    end: int
    form_surface: str
    paraphrase: str  # paraphrase with slots filled
    intended_meaning: str
    usage: str  # figurative | literal | uncertain
    usage_score: float
    entry_confidence: float
    review_status: str
    figurative_cues_found: list[str] = field(default_factory=list)
    literal_cues_found: list[str] = field(default_factory=list)
    literal_follower_found: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _fill_slots(paraphrase: str, groups: dict) -> str:
    from app.modules.idiom_lexicon import poss_to_obj

    poss = groups.get("poss")
    if poss:
        paraphrase = paraphrase.replace("{poss}", poss).replace("{obj}", poss_to_obj(poss))
    for name in ("akk", "dat", "gap", "gap2"):
        if groups.get(name) is not None:
            paraphrase = paraphrase.replace("{" + name + "}", groups[name])
    return paraphrase


class IdiomDetector:
    def __init__(self, entries: list[IdiomEntry] | None = None, config: IdiomConfig | None = None):
        self.entries = entries if entries is not None else load_lexicon()[1]
        self.config = config or IdiomConfig()

    def _assess(self, entry: IdiomEntry, text: str, start: int, end: int, context: list[str],
                slot_text: str = "") -> tuple:
        cfg = self.config
        # Evidence = the sentence without the idiom span, plus words captured by object slots
        # ("nimmt das Kind auf den Arm" -> "Kind"), plus any provided context.
        outside = text[:start] + " " + text[end:] + " " + slot_text
        toks = tokens(outside) + [t for c in context for t in tokens(c)]
        joined = " ".join(toks)
        fig = [c for c in entry.figurative_cues if cue_matches(c, toks, joined)]
        lit = [c for c in entry.literal_cues if cue_matches(c, toks, joined)]
        follower = None
        after = TOKEN_RE.findall(normalize_same_length(text[end:]))
        if after and after[0].lower() in {f.lower() for f in entry.literal_followers}:
            follower = after[0].lower()

        score = entry.figurative_prior
        score += min(cfg.max_figurative_bonus, cfg.figurative_cue_weight * len(fig))
        score -= cfg.literal_cue_weight * len(lit)
        if follower:
            score -= cfg.literal_follower_weight
        score = round(max(0.0, min(1.0, score)), 3)
        if score >= cfg.figurative_threshold:
            usage = "figurative"
        elif score <= cfg.literal_threshold:
            usage = "literal"
        else:
            usage = "uncertain"
        return usage, score, fig, lit, follower

    def detect(self, text: str, source_lang: str, context: list[str] | None = None) -> list[IdiomCandidate]:
        context = context or []
        norm = normalize_same_length(text)
        found: list[IdiomCandidate] = []
        for entry in self.entries:
            if entry.source_language != source_lang or entry.review_status == "rejected":
                continue
            best = None
            for form in entry.forms:
                for m in form.regex.finditer(norm):
                    # keep the longest match per entry per position
                    if best is None or (m.end() - m.start()) > (best[0].end() - best[0].start()):
                        best = (m, form)
            if best is None:
                continue
            m, form = best
            from app.modules.idiom_lexicon import SLOT_VALUE_NAMES

            slot_text = " ".join(v for k, v in m.groupdict().items() if k in SLOT_VALUE_NAMES and v)
            usage, score, fig, lit, follower = self._assess(entry, norm, m.start(), m.end(), context, slot_text)
            found.append(
                IdiomCandidate(
                    idiom_id=entry.idiom_id, expression=entry.expression, matched_text=text[m.start():m.end()],
                    start=m.start(), end=m.end(), form_surface=form.surface,
                    paraphrase=_fill_slots(form.paraphrase, m.groupdict()),
                    intended_meaning=entry.intended_meaning, usage=usage, usage_score=score,
                    entry_confidence=entry.confidence, review_status=entry.review_status,
                    figurative_cues_found=fig, literal_cues_found=lit, literal_follower_found=follower,
                )
            )
        found.sort(key=lambda c: c.start)
        return found
