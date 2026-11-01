import os

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_engine
from app.main import app
from app.translation.nllb_engine import TranslationResult


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_MODEL_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="real-model test; set RUN_MODEL_TESTS=1 to run")
    for item in items:
        if "model" in item.keywords:
            item.add_marker(skip)


class FakeEngine:
    """MOCK backend for unit tests. Does NOT translate; returns a tagged echo."""

    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    @property
    def is_loaded(self):
        return True

    def translate_batch(self, texts, source_lang, target_lang):
        self.calls.append((list(texts), source_lang, target_lang))
        if self.fail:
            return [TranslationResult(t, "", source_lang, target_lang, "error", 0.0, error="boom") for t in texts]
        return [
            TranslationResult(t, f"[{target_lang}] {t}", source_lang, target_lang, "ok", 1.0, 3, 4)
            for t in texts
        ]

    def translate(self, text, source_lang, target_lang):
        return self.translate_batch([text], source_lang, target_lang)[0]

    def info(self):
        return {
            "model_id": "fake",
            "requested_revision": "fake",
            "resolved_revision": "fake",
            "loaded": True,
            "device": "none",
            "load_seconds": None,
            "batch_size": 8,
            "generation_config": {"num_beams": 4},
        }


@pytest.fixture
def fake_engine():
    return FakeEngine()


@pytest.fixture
def client(fake_engine):
    app.dependency_overrides[get_engine] = lambda: fake_engine
    yield TestClient(app)
    app.dependency_overrides.clear()
