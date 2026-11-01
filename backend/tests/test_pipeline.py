"""Pipeline integration with a MOCKED translation engine."""
from app.pipeline import PipelineConfig, SemanticPipeline
from tests.conftest import FakeEngine


def run(text, **cfg):
    eng = FakeEngine()
    pr = SemanticPipeline(eng, PipelineConfig(**cfg)).run(text, "eng_Latn", "hin_Deva", example_id="T1")
    return pr, eng


def test_paraphrase_reaches_engine_and_record_is_complete():
    pr, eng = run("She spilled the beans about the party.", idiom_mode="paraphrase")
    assert eng.calls[0][0] == ["She revealed the secret about the party."]
    r = pr.record
    for key in ["example_id", "active_modules", "module_predictions", "confidence_scores", "thresholds",
                "controller_decision", "original_sentence", "modified_sentence", "abstention_reason", "final_translation"]:
        assert key in r
    assert r["controller_decision"] == "INTERVENE" and r["condition"] == "B_idiom_paraphrase"
    assert r["original_sentence"] == "She spilled the beans about the party."


def test_hint_mode():
    pr, eng = run("She spilled the beans about the party.", idiom_mode="hint")
    assert eng.calls[0][0] == ["She spilled the beans (revealed the secret) about the party."]


def test_baseline_condition_sends_original():
    pr, eng = run("She spilled the beans.", idiom_enabled=False)
    assert eng.calls[0][0] == ["She spilled the beans."]
    assert pr.record["condition"] == "A_baseline" and pr.record["controller_decision"] == "PASS_THROUGH"


def test_ordinary_sentence_unchanged():
    pr, eng = run("The weather is very pleasant today.")
    assert pr.record["modified_sentence"] is None and eng.calls[0][0] == ["The weather is very pleasant today."]


def test_events_cover_every_stage_in_order():
    pr, _ = run("She spilled the beans.")
    assert [e["stage"] for e in pr.events] == ["input", "idiom_detection", "context_analysis", "controller", "translation", "output"]
