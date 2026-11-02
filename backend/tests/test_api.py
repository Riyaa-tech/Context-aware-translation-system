"""API validation tests. Translation engine is MOCKED (FakeEngine)."""
import pytest

from app.api.deps import get_engine
from app.main import app


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_languages(client):
    body = client.get("/api/languages").json()
    assert len(body["directions"]) == 10
    assert body["allow_planned_directions"] is False


def test_baseline_ok_with_aliases(client, fake_engine):
    r = client.post("/api/translate/baseline", json={"text": "  Hello  ", "source_lang": "en", "target_lang": "hi"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["condition"] == "A_baseline"
    assert body["source_lang"] == "eng_Latn" and body["target_lang"] == "hin_Deva"
    assert body["source_text"] == "Hello"
    assert fake_engine.calls == [(["Hello"], "eng_Latn", "hin_Deva")]


def test_blank_text_rejected(client):
    r = client.post("/api/translate/baseline", json={"text": "   ", "source_lang": "en", "target_lang": "hi"})
    assert r.status_code == 422


def test_too_long_text_rejected(client):
    r = client.post("/api/translate/baseline", json={"text": "a" * 2001, "source_lang": "en", "target_lang": "hi"})
    assert r.status_code == 422


def test_unknown_language(client):
    r = client.post("/api/translate/baseline", json={"text": "Hi", "source_lang": "xx", "target_lang": "hi"})
    assert r.status_code == 400 and "Unknown language" in r.json()["detail"]


def test_planned_direction_rejected(client):
    r = client.post("/api/translate/baseline", json={"text": "Bonjour", "source_lang": "fr", "target_lang": "ar"})
    assert r.status_code == 400 and "not yet tested" in r.json()["detail"]


def test_engine_error_is_reported(client):
    from tests.conftest import FakeEngine

    app.dependency_overrides[get_engine] = lambda: FakeEngine(fail=True)
    r = client.post("/api/translate/baseline", json={"text": "Hi", "source_lang": "en", "target_lang": "de"})
    assert r.status_code == 500 and "boom" in r.json()["detail"]


def test_german_directions_accepted(client, fake_engine):
    for s, t in (("en", "de"), ("de", "en")):
        r = client.post("/api/translate/baseline", json={"text": "Hallo Welt", "source_lang": s, "target_lang": t})
        assert r.status_code == 200, r.text
    assert fake_engine.calls[-1][1:] == ("deu_Latn", "eng_Latn")


@pytest.mark.parametrize("src,tgt", [("en", "es"), ("es", "en"), ("spa_Latn", "eng_Latn")])
def test_spanish_directions_rejected(client, src, tgt):
    r = client.post("/api/translate/baseline", json={"text": "Hola", "source_lang": src, "target_lang": tgt})
    assert r.status_code == 400 and "Spanish was removed" in r.json()["detail"]
