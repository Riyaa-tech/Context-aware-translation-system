"""Shared dependencies. Tests override `get_engine` with a fake backend."""
from __future__ import annotations

from functools import lru_cache

from app.config.settings import Settings, get_settings
from app.translation.nllb_engine import NLLBEngine


@lru_cache(maxsize=1)
def _engine_singleton() -> NLLBEngine:
    return NLLBEngine(get_settings())


def get_engine() -> NLLBEngine:
    return _engine_singleton()


def get_app_settings() -> Settings:
    return get_settings()
