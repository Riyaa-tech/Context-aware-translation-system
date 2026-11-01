"""Unit tests: controller thresholds, abstention and conflicts (no model)."""
from dataclasses import replace

from app.controller.semantic_controller import ABSTAIN, INTERVENE, PASS_THROUGH, ControllerConfig, SemanticController
from app.modules.idiom_detector import IdiomCandidate, IdiomDetector

DET = IdiomDetector()
CTRL = SemanticController()


def cand(**kw):
    base = dict(idiom_id="EN_X", expression="x", matched_text="x", start=0, end=5, form_surface="x",
                paraphrase="p", intended_meaning="m", usage="figurative", usage_score=0.8,
                entry_confidence=0.9, review_status="draft")
    base.update(kw)
    return IdiomCandidate(**base)


def test_no_candidates_pass_through():
    assert CTRL.decide([]).decision == PASS_THROUGH
    assert CTRL.decide(DET.detect("The weather is nice.", "eng_Latn")).decision == PASS_THROUGH


def test_figurative_intervenes():
    out = CTRL.decide(DET.detect("She spilled the beans about the party.", "eng_Latn"))
    assert out.decision == INTERVENE and out.accepted_idioms[0].idiom_id == "EN_001"


def test_literal_passes_through_not_abstain():
    out = CTRL.decide(DET.detect("He spilled the beans on the kitchen floor.", "eng_Latn"))
    assert out.decision == PASS_THROUGH
    assert out.span_decisions[0].action == "reject_literal"


def test_uncertain_abstains_with_reason():
    out = CTRL.decide(DET.detect("She told me she spilled the beans on the floor.", "eng_Latn"))
    assert out.decision == ABSTAIN and "EN_001" in out.abstention_reason


def test_threshold_is_configurable():
    c = cand(usage_score=0.7)
    assert SemanticController(ControllerConfig(idiom_intervene_threshold=0.75)).decide([c]).decision == ABSTAIN
    assert SemanticController(ControllerConfig(idiom_intervene_threshold=0.65)).decide([c]).decision == INTERVENE


def test_low_entry_confidence_and_review_status_rejected():
    assert CTRL.decide([cand(entry_confidence=0.2)]).span_decisions[0].action == "reject_low_confidence"
    strict = SemanticController(ControllerConfig(idiom_allowed_review_statuses=("reviewed",)))
    out = strict.decide([cand()])
    assert out.decision == PASS_THROUGH and out.span_decisions[0].action == "reject_review_status"


def test_overlapping_entries_conflict_abstains():
    a = cand(idiom_id="A", start=0, end=10)
    b = cand(idiom_id="B", start=5, end=15)
    out = CTRL.decide([a, b])
    assert out.decision == ABSTAIN and out.conflicts
    assert {s.action for s in out.span_decisions} == {"abstain_conflict"}


def test_partial_intervention_when_one_span_uncertain():
    good = cand(idiom_id="G", start=0, end=5)
    unsure = cand(idiom_id="U", start=10, end=15, usage="uncertain", usage_score=0.5)
    out = CTRL.decide([good, unsure])
    assert out.decision == INTERVENE and [c.idiom_id for c in out.accepted_idioms] == ["G"]
    assert {s.action for s in out.span_decisions} == {"accept", "abstain_uncertain"}


def test_deterministic():
    cs = DET.detect("The exam was a piece of cake.", "eng_Latn")
    assert CTRL.decide(cs).as_dict() == CTRL.decide(cs).as_dict()
