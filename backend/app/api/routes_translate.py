from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_app_settings, get_engine
from app.config.languages import LanguageError, check_direction, normalize_code
from app.pipeline import PipelineConfig, SemanticPipeline
from app.schemas.translation import (
    CompareResponse,
    EnhancedRequest,
    EnhancedResponse,
    TranslateRequest,
    TranslateResponse,
)

router = APIRouter(prefix="/api/translate", tags=["translate"])


def resolve_direction(req: TranslateRequest, settings) -> tuple[str, str]:
    try:
        src = normalize_code(req.source_lang)
        tgt = normalize_code(req.target_lang)
        check_direction(src, tgt, allow_planned=settings.allow_planned_directions)
    except LanguageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return src, tgt


def _baseline_response(result, engine) -> TranslateResponse:
    info = engine.info()
    return TranslateResponse(
        source_text=result.source_text, translation=result.translation, source_lang=result.source_lang,
        target_lang=result.target_lang, status=result.status, latency_ms=result.latency_ms,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens, warnings=result.warnings,
        error=result.error, model_id=info["model_id"], model_revision=info["resolved_revision"],
        generation_config=info["generation_config"],
    )


def _check(result):
    if result.status == "error":
        raise HTTPException(status_code=500, detail=f"Translation failed: {result.error}")


async def _call(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except HTTPException:
        raise
    except Exception as e:  # model failed to load, etc.
        raise HTTPException(status_code=503, detail=f"Translation engine unavailable: {type(e).__name__}: {e}") from e


@router.post("/baseline", response_model=TranslateResponse)
async def translate_baseline(req: TranslateRequest, engine=Depends(get_engine), settings=Depends(get_app_settings)):
    """Condition A: the unmodified NLLB-200 model. No semantic modules are applied."""
    src, tgt = resolve_direction(req, settings)
    result = await _call(engine.translate, req.text, src, tgt)
    _check(result)
    return _baseline_response(result, engine)


def _pipeline_for(req: EnhancedRequest, engine) -> SemanticPipeline:
    cfg = PipelineConfig(idiom_enabled="idiom" in req.modules, idiom_mode=req.idiom_mode,
                         context_mode=req.context_mode if "context" in req.modules else "none")
    return SemanticPipeline(engine, cfg)


def _enhanced_response(pr, engine) -> EnhancedResponse:
    info = engine.info()
    r = pr.record
    return EnhancedResponse(
        condition=r["condition"], source_text=r["original_sentence"], translation=r["final_translation"],
        source_lang=r["source_lang"], target_lang=r["target_lang"], status=r["translation_status"],
        controller_decision=r["controller_decision"], nllb_input=r["nllb_input"], record=r, events=pr.events,
        model_id=info["model_id"], model_revision=info["resolved_revision"],
    )


@router.post("/enhanced", response_model=EnhancedResponse)
async def translate_enhanced(req: EnhancedRequest, engine=Depends(get_engine), settings=Depends(get_app_settings)):
    """Proposed system: semantic modules + controller in front of the unchanged NLLB-200 model."""
    src, tgt = resolve_direction(req, settings)
    pipe = _pipeline_for(req, engine)
    pr = await _call(pipe.run, req.text, src, tgt, req.context)
    _check(pr.translation_result)
    return _enhanced_response(pr, engine)


@router.post("/compare", response_model=CompareResponse)
async def translate_compare(req: EnhancedRequest, engine=Depends(get_engine), settings=Depends(get_app_settings)):
    """Baseline and enhanced outputs for the same input, side by side."""
    src, tgt = resolve_direction(req, settings)
    base = await _call(engine.translate, req.text, src, tgt)
    _check(base)
    pipe = _pipeline_for(req, engine)
    pr = await _call(pipe.run, req.text, src, tgt, req.context)
    _check(pr.translation_result)
    enhanced = _enhanced_response(pr, engine)
    return CompareResponse(
        baseline=_baseline_response(base, engine), enhanced=enhanced,
        outputs_differ=base.translation != enhanced.translation,
        enhanced_input_unchanged=enhanced.nllb_input == req.text,
    )
