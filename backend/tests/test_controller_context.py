"""Controller with context module and cross-module conflicts (no model)."""
from app.controller.semantic_controller import ABSTAIN, INTERVENE, PASS_THROUGH, SemanticController
from app.modules.context_selector import ContextSelector
from app.modules.idiom_detector import IdiomDetector

CTRL, SEL, DET = SemanticController(), ContextSelector(), IdiomDetector()


def decide(text, ctx=None):
    return CTRL.decide(DET.detect(text, "eng_Latn", ctx), SEL.analyze(text, "eng_Latn", ctx))


def test_context_intervention():
    out = decide("He went to the bank.", ["The fisherman sat beside the river."])
    assert out.decision == INTERVENE and out.accepted_context_words[0].word_id == "EN_W_bank"


def test_irrelevant_and_missing_context_abstain():
    out = decide("He went to the bank.", ["The weather was lovely."])
    assert out.decision == ABSTAIN and "context:EN_W_bank" in out.abstention_reason
    assert decide("He went to the bank.").span_decisions[0].action == "abstain_insufficient"


def test_resolved_dominant_sense_is_pass_through():
    out = decide("He went to the bank.", ["He needed to deposit his salary."])
    assert out.decision == PASS_THROUGH and out.span_decisions[0].action == "resolved_no_rewrite"


def test_idiom_and_context_both_intervene_on_different_spans():
    out = decide("She spilled the beans at the bank.", ["They had a picnic by the river.", "It was a secret plan."])
    assert out.decision == INTERVENE
    assert out.accepted_idioms and out.accepted_context_words


def test_tennis_context_makes_idiom_literal_not_conflict():
    # Real behaviour: tennis is a literal cue for the idiom, and 'ball' resolves 'court' in-sentence.
    out = decide("The ball is in your court.", ["We were playing tennis."])
    assert out.decision == PASS_THROUGH and not out.conflicts


def test_cross_module_conflict_abstains():
    """Synthetic inputs: both modules propose rewrites of overlapping text."""
    from app.modules.context_selector import RELEVANT_CONTEXT_SELECTED, ContextAnalysis, WordAnalysis
    from tests.test_controller import cand

    idiom = cand(idiom_id="EN_018", start=0, end=26, matched_text="The ball is in your court")
    word = WordAnalysis("EN_W_court", "court", "court", 20, 25, RELEVANT_CONTEXT_SELECTED, {},
                        resolved_sense="court.law", replacement="court of law", reason="law context")
    out = CTRL.decide([idiom], ContextAnalysis(RELEVANT_CONTEXT_SELECTED, [word], [], []))
    assert out.decision == ABSTAIN and out.conflicts
    assert {(s.module, s.action) for s in out.span_decisions} == {("idiom", "abstain_conflict"), ("context", "abstain_conflict")}
