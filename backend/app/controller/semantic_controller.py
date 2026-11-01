"""Semantic Preservation Controller (paper Section IV-H).

Decides, deterministically, for each sentence:
  PASS_THROUGH  - send the original sentence to NLLB unchanged
  INTERVENE     - apply a reviewed hint / controlled paraphrase
  ABSTAIN       - a trigger fired but evidence is weak or modules/entries conflict: keep the original

Every decision is returned with the evidence and thresholds that produced it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.modules.context_selector import (
    CONTEXT_AMBIGUOUS,
    CONTEXT_INSUFFICIENT,
    CONTEXT_IRRELEVANT,
    RELEVANT_CONTEXT_SELECTED,
    ContextAnalysis,
    WordAnalysis,
)
from app.modules.idiom_detector import IdiomCandidate

PASS_THROUGH = "PASS_THROUGH"
INTERVENE = "INTERVENE"
ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ControllerConfig:
    idiom_intervene_threshold: float = 0.60  # minimum usage score to act on an idiom
    idiom_min_entry_confidence: float = 0.50  # minimum lexicon rule score for the entry
    # Pilot default accepts "draft" entries so the module can be exercised before human review.
    # Every decision record states the review_status of the entries used.
    idiom_allowed_review_statuses: tuple[str, ...] = ("reviewed", "draft")

    def as_dict(self) -> dict:
        d = asdict(self)
        d["idiom_allowed_review_statuses"] = list(self.idiom_allowed_review_statuses)
        return d


@dataclass
class SpanDecision:
    module: str  # idiom | context
    item_id: str | None  # idiom_id or word_id
    span: tuple[int, int]
    # idiom: accept | reject_literal | abstain_uncertain | abstain_conflict | reject_low_confidence | reject_review_status
    # context: accept | no_context_required | resolved_no_rewrite | abstain_irrelevant | abstain_insufficient
    #          | abstain_ambiguous | abstain_conflict
    action: str
    reason: str


@dataclass
class ControllerOutput:
    decision: str
    accepted_idioms: list[IdiomCandidate] = field(default_factory=list)
    accepted_context_words: list[WordAnalysis] = field(default_factory=list)
    span_decisions: list[SpanDecision] = field(default_factory=list)
    abstention_reason: str | None = None
    conflicts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "accepted_idioms": [c.idiom_id for c in self.accepted_idioms],
            "accepted_context_words": [w.word_id for w in self.accepted_context_words],
            "span_decisions": [asdict(s) for s in self.span_decisions],
            "abstention_reason": self.abstention_reason,
            "conflicts": self.conflicts,
        }


def _overlaps(a: IdiomCandidate, b: IdiomCandidate) -> bool:
    return a.start < b.end and b.start < a.end


class SemanticController:
    def __init__(self, config: ControllerConfig | None = None):
        self.config = config or ControllerConfig()

    def decide(self, idiom_candidates: list[IdiomCandidate] | None,
               context_analysis: ContextAnalysis | None = None) -> ControllerOutput:
        cfg = self.config
        cands = idiom_candidates or []
        spans: list[SpanDecision] = []
        conflicts: list[str] = []

        # ---- idiom module ----
        conflicted: set[str] = set()
        for i, a in enumerate(cands):  # overlapping lexicon matches = conflicting readings
            for b in cands[i + 1:]:
                if _overlaps(a, b):
                    conflicted.update({a.idiom_id, b.idiom_id})
                    conflicts.append(f"{a.idiom_id} overlaps {b.idiom_id} ('{a.matched_text}' / '{b.matched_text}')")
        accepted: list[IdiomCandidate] = []
        for c in cands:
            span = (c.start, c.end)
            if c.idiom_id in conflicted:
                spans.append(SpanDecision("idiom", c.idiom_id, span, "abstain_conflict", "overlapping lexicon matches"))
            elif c.usage == "literal":
                spans.append(SpanDecision("idiom", c.idiom_id, span, "reject_literal",
                                          f"literal usage (score {c.usage_score}; literal cues {c.literal_cues_found}"
                                          f"{', follower ' + repr(c.literal_follower_found) if c.literal_follower_found else ''})"))
            elif c.usage == "uncertain" or c.usage_score < cfg.idiom_intervene_threshold:
                spans.append(SpanDecision("idiom", c.idiom_id, span, "abstain_uncertain",
                                          f"usage score {c.usage_score} below intervene threshold {cfg.idiom_intervene_threshold}"))
            elif c.entry_confidence < cfg.idiom_min_entry_confidence:
                spans.append(SpanDecision("idiom", c.idiom_id, span, "reject_low_confidence",
                                          f"entry confidence {c.entry_confidence} < {cfg.idiom_min_entry_confidence}"))
            elif c.review_status not in cfg.idiom_allowed_review_statuses:
                spans.append(SpanDecision("idiom", c.idiom_id, span, "reject_review_status",
                                          f"review_status '{c.review_status}' not allowed"))
            else:
                spans.append(SpanDecision("idiom", c.idiom_id, span, "accept",
                                          f"figurative usage (score {c.usage_score} >= {cfg.idiom_intervene_threshold})"))
                accepted.append(c)

        # ---- context module ----
        ctx_accepted: list[WordAnalysis] = []
        for w in (context_analysis.words if context_analysis else []):
            span = (w.start, w.end)
            if w.state == RELEVANT_CONTEXT_SELECTED and w.replacement:
                action = "accept"
            elif w.state == RELEVANT_CONTEXT_SELECTED:
                action = "resolved_no_rewrite"
            else:
                action = {CONTEXT_IRRELEVANT: "abstain_irrelevant", CONTEXT_INSUFFICIENT: "abstain_insufficient",
                          CONTEXT_AMBIGUOUS: "abstain_ambiguous"}.get(w.state, "no_context_required")
            spans.append(SpanDecision("context", w.word_id, span, action, w.reason))
            if action == "accept":
                ctx_accepted.append(w)

        # ---- cross-module conflicts: both modules want to rewrite overlapping text ----
        for c in list(accepted):
            for w in list(ctx_accepted):
                if c.start < w.end and w.start < c.end:
                    conflicts.append(f"idiom {c.idiom_id} and context word {w.word_id} both rewrite '{w.matched_text}'")
                    accepted.remove(c)
                    ctx_accepted.remove(w)
                    for s in spans:
                        if s.item_id in (c.idiom_id, w.word_id) and s.action == "accept":
                            s.action, s.reason = "abstain_conflict", "modules propose incompatible rewrites of the same span"

        if accepted or ctx_accepted:
            return ControllerOutput(INTERVENE, accepted, ctx_accepted, spans, None, conflicts)
        abstains = [s for s in spans if s.action.startswith("abstain")]
        if abstains:
            return ControllerOutput(ABSTAIN, [], [], spans,
                                    "; ".join(f"{s.module}:{s.item_id}: {s.reason}" for s in abstains), conflicts)
        return ControllerOutput(PASS_THROUGH, [], [], spans, None, conflicts)
