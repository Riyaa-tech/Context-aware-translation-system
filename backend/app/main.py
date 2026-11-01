"""FastAPI entry point.  Run:  cd backend && uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path

from fastapi.responses import FileResponse

from app.api import (
    routes_annotations,
    routes_experiments,
    routes_health,
    routes_research,
    routes_resources,
    routes_translate,
)
from app.api.deps import get_engine
from app.config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().preload_model:
        get_engine().load()
    yield


app = FastAPI(
    title="Context-Aware NMT Research MVP",
    description="NLLB-200 baseline plus selective semantic modules (research prototype).",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(routes_health.router)
app.include_router(routes_translate.router)
app.include_router(routes_resources.router)
app.include_router(routes_experiments.router)
app.include_router(routes_annotations.router)
app.include_router(routes_research.router)

STATIC = Path(__file__).parent / "static"


@app.get("/annotate-lite", include_in_schema=False)
def annotate_page():
    """Minimal annotation page for human raters (the React frontend will offer the same workflow)."""
    return FileResponse(STATIC / "annotate.html")


# Serve the built React frontend (frontend/dist) when present, so the demo needs one server.
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Client-side routes fall back to index.html (API routes are matched first)."""
        if path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(404, "not found")
        f = FRONTEND / path
        return FileResponse(f if path and f.is_file() else FRONTEND / "index.html")
