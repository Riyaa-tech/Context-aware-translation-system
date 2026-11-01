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


class EnhancedRequest(TranslateRequest):
    context: list[str] = Field(default_factory=list, max_length=10, description="Preceding sentences, oldest first")
    idiom_mode: str = Field("hint", pattern="^(hint|paraphrase)$")
    modules: list[str] = Field(default_factory=lambda: ["idiom"], description="Semantic modules to enable")

    @field_validator("modules")
    @classmethod
    def known_modules(cls, v: list[str]) -> list[str]:
        allowed = {"idiom"}
        bad = [m for m in v if m not in allowed]
        if bad:
            raise ValueError(f"unknown or not-yet-implemented modules {bad}; available: {sorted(allowed)}")
        return v

    @field_validator("context")
    @classmethod
    def context_items(cls, v: list[str]) -> list[str]:
        return [c.strip() for c in v if c and c.strip()]


class EnhancedResponse(BaseModel):
    condition: str
    source_text: str
    translation: str
    source_lang: str
    target_lang: str
    status: str
    controller_decision: str
    nllb_input: str
    record: dict
    events: list[dict]
    model_id: str
    model_revision: str | None


class CompareResponse(BaseModel):
    baseline: TranslateResponse
    enhanced: EnhancedResponse
    outputs_differ: bool
    enhanced_input_unchanged: bool
