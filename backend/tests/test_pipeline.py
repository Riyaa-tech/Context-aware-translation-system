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


# ---- Milestone 3: context modes ----
from app.pipeline import extract_last_sentence  # noqa: E402

RIVER = ["The fisherman sat beside the river."]


def run_ctx(text, ctx, **cfg):
    eng = FakeEngine()
    pr = SemanticPipeline(eng, PipelineConfig(**cfg)).run(text, "eng_Latn", "hin_Deva", context=ctx)
    return pr, eng


def test_selected_context_rewrites_single_sentence():
    pr, eng = run_ctx("He went to the bank.", RIVER, idiom_enabled=False, context_mode="selected")
    assert eng.calls[0][0] == ["He went to the riverbank."]  # NLLB still receives ONE sentence
    r = pr.record
    assert r["condition"] == "C_context_selected" and r["context_state"] == "RELEVANT_CONTEXT_SELECTED"
    assert r["selected_context"] == RIVER and r["module_predictions"]["context"][0]["resolved_sense"] == "bank.river"


def test_concat_control_prepends_window_and_extracts_last_sentence():
    pr, eng = run_ctx("He went to the bank.", ["A b.", "The fisherman sat beside the river."],
                      idiom_enabled=False, context_mode="concat")
    assert eng.calls[0][0] == ["A b. The fisherman sat beside the river. He went to the bank."]
    r = pr.record
    assert r["condition"] == "C_context_concat"
    assert r["final_translation"] == "He went to the bank."  # fake echo -> last sentence
    assert r["raw_concat_translation"].startswith("[hin_Deva]")


def test_concat_without_context_is_plain_sentence():
    pr, eng = run_ctx("He went to the bank.", [], idiom_enabled=False, context_mode="concat")
    assert eng.calls[0][0] == ["He went to the bank."] and "raw_concat_translation" not in pr.record


def test_combined_condition_name():
    assert PipelineConfig(context_mode="selected").condition_name == "D_idiom_paraphrase+context_selected"
    assert PipelineConfig(idiom_enabled=False).condition_name == "A_baseline"
    assert PipelineConfig(idiom_mode="hint").condition_name == "B_idiom_hint"


def test_extract_last_sentence_warns_on_mismatch():
    assert extract_last_sentence("Uno. Dos. Tres.", 3) == ("Tres.", [])
    last, w = extract_last_sentence("Uno dos. Tres.", 3)
    assert last == "Tres." and w and "alignment uncertain" in w[0]
    assert extract_last_sentence("एक। दो।", 2)[0] == "दो।"
