"""FastAPI entry point.  Run:  cd backend && uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_health, routes_translate
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
