"""REAL-MODEL smoke tests (not mocked). Run with:  RUN_MODEL_TESTS=1 pytest -m model -s"""
import re

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_engine
from app.main import app

pytestmark = pytest.mark.model

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")

CASES = [
    ("eng_Latn", "hin_Deva", "The weather is very pleasant today.", DEVANAGARI),
    ("hin_Deva", "eng_Latn", "आज मौसम बहुत सुहाना है।", LATIN),
    ("eng_Latn", "deu_Latn", "The weather is very pleasant today.", LATIN),
    ("deu_Latn", "eng_Latn", "Heute ist das Wetter sehr angenehm.", LATIN),
]


@pytest.fixture(scope="module")
def engine():
    e = get_engine()
    e.load()
    return e


@pytest.mark.parametrize("src,tgt,text,script", CASES)
def test_real_translation_each_enabled_direction(engine, src, tgt, text, script):
    r = engine.translate(text, src, tgt)
    print(f"\n[{src}->{tgt}] {text!r} -> {r.translation!r} ({r.latency_ms} ms)")
    assert r.status == "ok"
    assert r.translation and r.translation != text
    assert script.search(r.translation), "output is not in the expected script"


def test_hindi_output_is_not_english(engine):
    r = engine.translate("I like reading books.", "eng_Latn", "hin_Deva")
    assert len(DEVANAGARI.findall(r.translation)) > len(LATIN.findall(r.translation))


def test_deterministic_across_calls_and_batching(engine):
    texts = ["She finally spilled the beans.", "He went to the bank."]
    single = [engine.translate(t, "eng_Latn", "deu_Latn").translation for t in texts]
    batched = [r.translation for r in engine.translate_batch(texts, "eng_Latn", "deu_Latn")]
    again = [engine.translate(t, "eng_Latn", "deu_Latn").translation for t in texts]
    print(f"\nsingle={single}\nbatched={batched}")
    assert single == again
    # Padding in a batch can in rare cases change beam search results; record if so.
    if single != batched:
        pytest.xfail(f"batched output differs from single: {single} vs {batched}")


def test_api_end_to_end_real_model(engine):
    app.dependency_overrides.clear()
    c = TestClient(app)
    r = c.post("/api/translate/baseline", json={"text": "Good morning, how are you?", "source_lang": "en", "target_lang": "hi"})
    assert r.status_code == 200, r.text
    body = r.json()
    print(f"\nAPI response: {body['translation']!r}, revision={body['model_revision']}")
    assert DEVANAGARI.search(body["translation"])
    assert body["model_revision"].startswith("f8d333a")


# ---- Milestone 2: idiom pipeline with the REAL model ----
from app.pipeline import PipelineConfig, SemanticPipeline  # noqa: E402


def test_real_idiom_paraphrase_changes_input_and_output(engine):
    text = "Fixing that bug was a piece of cake."
    base = engine.translate(text, "eng_Latn", "hin_Deva").translation
    pr = SemanticPipeline(engine, PipelineConfig(idiom_mode="paraphrase")).run(text, "eng_Latn", "hin_Deva")
    print(f"\nbaseline={base!r}\nparaphrase={pr.record['final_translation']!r}")
    assert pr.record["controller_decision"] == "INTERVENE"
    assert pr.record["nllb_input"] == "Fixing that bug was very easy."
    assert pr.record["final_translation"] != base


def test_real_literal_control_identical_to_baseline(engine):
    text = "I'd like a piece of cake with my coffee."
    base = engine.translate(text, "eng_Latn", "hin_Deva").translation
    pr = SemanticPipeline(engine, PipelineConfig(idiom_mode="paraphrase")).run(text, "eng_Latn", "hin_Deva")
    assert pr.record["controller_decision"] == "PASS_THROUGH"
    assert pr.record["final_translation"] == base


# ---- Milestone 3: context module with the REAL model ----
def test_real_selected_context_riverbank(engine):
    text, ctx = "He went to the bank.", ["The fisherman sat beside the river."]
    base = engine.translate(text, "eng_Latn", "hin_Deva").translation
    pr = SemanticPipeline(engine, PipelineConfig(idiom_enabled=False, context_mode="selected")).run(text, "eng_Latn", "hin_Deva", ctx)
    print(f"\nbaseline={base!r}\nselected={pr.record['final_translation']!r}")
    assert pr.record["nllb_input"] == "He went to the riverbank."
    assert pr.record["final_translation"] != base


def test_real_irrelevant_context_leaves_output_unchanged(engine):
    text = "He went to the bank."
    base = engine.translate(text, "eng_Latn", "hin_Deva").translation
    pr = SemanticPipeline(engine, PipelineConfig(idiom_enabled=False, context_mode="selected")).run(
        text, "eng_Latn", "hin_Deva", ["My cousin called me yesterday."])
    assert pr.record["controller_decision"] == "ABSTAIN" and pr.record["final_translation"] == base


def test_real_combined_condition(engine):
    text = "She spilled the beans at the bank."
    ctx = ["They had a picnic by the river.", "It was meant to be a secret."]
    pr = SemanticPipeline(engine, PipelineConfig(context_mode="selected")).run(text, "eng_Latn", "deu_Latn", ctx)
    print(f"\ncombined input={pr.record['nllb_input']!r} -> {pr.record['final_translation']!r}")
    assert pr.record["condition"] == "D_idiom_paraphrase+context_selected"
    assert pr.record["nllb_input"] == "She revealed the secret at the riverbank."



# ---- German scope: REAL model ----
GERMAN_WORDS = re.compile(r"\b(der|die|das|ist|und|nicht|ein|eine|sehr|heute)\b", re.IGNORECASE)


def test_real_english_to_german_is_german(engine):
    r = engine.translate("The weather is very pleasant today and the children are playing outside.", "eng_Latn", "deu_Latn")
    print(f"\nen->de: {r.translation!r}")
    assert r.status == "ok" and GERMAN_WORDS.search(r.translation)


def test_real_german_idiom_paraphrase_changes_output(engine):
    text = "Das glaube ich dir nicht, du nimmst mich auf den Arm!"
    base = engine.translate(text, "deu_Latn", "eng_Latn").translation
    pr = SemanticPipeline(engine, PipelineConfig(idiom_mode="paraphrase")).run(text, "deu_Latn", "eng_Latn")
    print(f"\nbaseline={base!r}\nparaphrase={pr.record['final_translation']!r}")
    assert pr.record["controller_decision"] == "INTERVENE"
    assert pr.record["nllb_input"] == "Das glaube ich dir nicht, du hältst mich zum Narren!"
    assert pr.record["final_translation"] != base


def test_real_german_literal_control_identical_to_baseline(engine):
    text = "Die Mutter nimmt das weinende Kind auf den Arm."
    base = engine.translate(text, "deu_Latn", "eng_Latn").translation
    pr = SemanticPipeline(engine, PipelineConfig(idiom_mode="paraphrase")).run(text, "deu_Latn", "eng_Latn")
    assert pr.record["controller_decision"] == "PASS_THROUGH" and pr.record["final_translation"] == base
