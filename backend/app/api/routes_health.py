from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_engine
from app.config.languages import DIRECTIONS, LANGUAGES
from app.translation.run_info import collect_run_info

router = APIRouter()


@router.get("/health")
def health(engine=Depends(get_engine)):
    info = engine.info()
    return {"status": "ok", "model_loaded": engine.is_loaded, "model_state": info.get("state", "ready" if engine.is_loaded else "not_loaded"),
            "model_error": info.get("load_error"), "model": info}


@router.get("/api/languages")
def languages(settings=Depends(get_app_settings)):
    return {
        "languages": [{"code": c, "name": n} for c, n in LANGUAGES.items()],
        "directions": [
            {"source": d.source, "target": d.target, "status": d.status} for d in DIRECTIONS
        ],
        "allow_planned_directions": settings.allow_planned_directions,
    }


@router.get("/api/system/run-info")
def run_info(engine=Depends(get_engine)):
    return collect_run_info(engine.info())
