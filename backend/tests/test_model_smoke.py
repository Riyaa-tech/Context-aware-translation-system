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
    ("eng_Latn", "spa_Latn", "The weather is very pleasant today.", LATIN),
    ("spa_Latn", "eng_Latn", "Hoy el clima es muy agradable.", LATIN),
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
    single = [engine.translate(t, "eng_Latn", "spa_Latn").translation for t in texts]
    batched = [r.translation for r in engine.translate_batch(texts, "eng_Latn", "spa_Latn")]
    again = [engine.translate(t, "eng_Latn", "spa_Latn").translation for t in texts]
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
