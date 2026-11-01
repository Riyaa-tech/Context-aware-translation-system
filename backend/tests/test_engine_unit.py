"""Unit tests for engine batching / failure handling. Model calls are MOCKED."""
from app.config.settings import Settings
from app.translation.nllb_engine import NLLBEngine, TranslationResult


def _engine(batch_size=2):
    e = NLLBEngine(Settings(batch_size=batch_size))
    e._model = object()  # pretend loaded; _generate is mocked below
    return e


def test_batches_and_preserves_order(monkeypatch):
    e = _engine(batch_size=2)
    seen = []

    def fake_generate(texts, s, t):
        seen.append(list(texts))
        return [TranslationResult(x, x.upper(), s, t, "ok", 1.0) for x in texts]

    monkeypatch.setattr(e, "_generate", fake_generate)
    out = e.translate_batch(["a", "b", "c"], "eng_Latn", "hin_Deva")
    assert [r.translation for r in out] == ["A", "B", "C"]
    assert seen == [["a", "b"], ["c"]]


def test_failed_items_are_kept_not_dropped(monkeypatch):
    e = _engine(batch_size=3)

    def fake_generate(texts, s, t):
        if len(texts) > 1 or texts[0] == "bad":
            raise RuntimeError("out of memory")
        return [TranslationResult(texts[0], "ok!", s, t, "ok", 1.0)]

    monkeypatch.setattr(e, "_generate", fake_generate)
    out = e.translate_batch(["x", "bad", "y"], "eng_Latn", "spa_Latn")
    assert len(out) == 3
    assert [r.status for r in out] == ["ok", "error", "ok"]
    assert "out of memory" in out[1].error


def test_empty_input_returns_empty():
    assert _engine().translate_batch([], "eng_Latn", "hin_Deva") == []


def test_generation_config_is_deterministic_by_default():
    g = Settings().generation
    assert g.do_sample is False and g.num_beams >= 1 and g.max_input_tokens == 512
