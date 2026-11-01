from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Sentence to translate")
    source_lang: str = Field(..., description="NLLB code (e.g. eng_Latn) or alias (en)")
    target_lang: str = Field(..., description="NLLB code (e.g. hin_Deva) or alias (hi)")

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v.strip()


class TranslateResponse(BaseModel):
    condition: str = "A_baseline"
    source_text: str
    translation: str
    source_lang: str
    target_lang: str
    status: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    warnings: list[str]
    error: str | None
    model_id: str
    model_revision: str | None
    generation_config: dict
