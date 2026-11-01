from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_app_settings, get_engine
from app.config.languages import LanguageError, check_direction, normalize_code
from app.schemas.translation import TranslateRequest, TranslateResponse

router = APIRouter(prefix="/api/translate", tags=["translate"])


def resolve_direction(req: TranslateRequest, settings) -> tuple[str, str]:
    try:
        src = normalize_code(req.source_lang)
        tgt = normalize_code(req.target_lang)
        check_direction(src, tgt, allow_planned=settings.allow_planned_directions)
    except LanguageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return src, tgt


@router.post("/baseline", response_model=TranslateResponse)
async def translate_baseline(req: TranslateRequest, engine=Depends(get_engine), settings=Depends(get_app_settings)):
    """Condition A: the unmodified NLLB-200 model. No semantic modules are applied."""
    src, tgt = resolve_direction(req, settings)
    try:
        result = await run_in_threadpool(engine.translate, req.text, src, tgt)
    except Exception as e:  # model failed to load, etc.
        raise HTTPException(status_code=503, detail=f"Translation engine unavailable: {type(e).__name__}: {e}") from e
    if result.status == "error":
        raise HTTPException(status_code=500, detail=f"Translation failed: {result.error}")
    info = engine.info()
    return TranslateResponse(
        source_text=result.source_text,
        translation=result.translation,
        source_lang=src,
        target_lang=tgt,
        status=result.status,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        warnings=result.warnings,
        error=result.error,
        model_id=info["model_id"],
        model_revision=info["resolved_revision"],
        generation_config=info["generation_config"],
    )
