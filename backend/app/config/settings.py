"""Runtime settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field


# Hugging Face commit of facebook/nllb-200-distilled-600M used for this project (resolved 2026-11-01).
PINNED_REVISION = "f8d333a098d19b4fd9a8b18f94170487ad3f821d"


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GenerationConfig:
    """Decoding settings. Must stay IDENTICAL across all experimental conditions."""

    num_beams: int = 4
    max_new_tokens: int = 256
    max_input_tokens: int = 512  # NLLB model card: trained on inputs of at most 512 tokens
    do_sample: bool = False  # deterministic decoding
    length_penalty: float = 1.0
    early_stopping: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Settings:
    model_id: str = field(default_factory=lambda: os.getenv("NLLB_MODEL_ID", "facebook/nllb-200-distilled-600M"))
    # Pinned Hugging Face commit for reproducibility (override with NLLB_MODEL_REVISION).
    model_revision: str = field(default_factory=lambda: os.getenv("NLLB_MODEL_REVISION", PINNED_REVISION))
    device: str = field(default_factory=lambda: os.getenv("NLLB_DEVICE", "auto"))  # auto | cpu | cuda
    batch_size: int = field(default_factory=lambda: int(os.getenv("NLLB_BATCH_SIZE", "8")))
    preload_model: bool = field(default_factory=lambda: _env_bool("NLLB_PRELOAD", False))
    allow_planned_directions: bool = field(default_factory=lambda: _env_bool("ALLOW_PLANNED_DIRECTIONS", False))
    max_text_chars: int = 2000
    seed: int = 1234
    generation: GenerationConfig = field(default_factory=GenerationConfig)


def get_settings() -> Settings:
    return Settings()
