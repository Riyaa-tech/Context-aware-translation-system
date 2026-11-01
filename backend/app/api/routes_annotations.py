"""Human annotation endpoints. Raters only ever see blinded items (no condition, no category)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.annotation.rubric import rubric
from app.annotation.store import AnnotationError
from app.api.deps import get_store
from app.experiments.runner import ExperimentError, read_predictions, read_run

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class BatchRequest(BaseModel):
    experiment_id: str
    conditions: list[str] | None = None  # default: all completed conditions
    categories: list[str] | None = None
    seed: int = 20261101
    note: str = ""


class AnnotationIn(BaseModel):
    item_id: str
    rater_id: str = Field(..., min_length=1, max_length=40)
    rating: str
    core_proposition: str | None = None
    figurative_meaning: str | None = None
    pragmatic_intent: str | None = None
    unsupported_addition: bool | None = None
    omission: bool | None = None
    primary_error: str | None = None
    secondary_errors: list[str] = Field(default_factory=list)
    comment: str | None = Field(None, max_length=2000)


@router.get("/rubric")
def get_rubric():
    return rubric()


@router.post("/batches", status_code=201)
def create_batch(req: BatchRequest, store=Depends(get_store)):
    try:
        m = read_run(req.experiment_id)
        conds = req.conditions or [c for c, s in m["conditions"].items() if s["status"] == "complete"]
        preds = {c: read_predictions(req.experiment_id, c) for c in conds}
        return store.create_batch(req.experiment_id, preds, seed=req.seed, categories=req.categories, note=req.note)
    except (ExperimentError, AnnotationError) as e:
        raise HTTPException(400, str(e)) from e


@router.get("/batches")
def batches(store=Depends(get_store)):
    return {"batches": store.list_batches()}


@router.get("")
def items(batch_id: str, rater_id: str, only_pending: bool = False, store=Depends(get_store)):
    try:
        return store.rater_items(batch_id, rater_id, only_pending)
    except AnnotationError as e:
        raise HTTPException(400, str(e)) from e


@router.post("")
def save(a: AnnotationIn, store=Depends(get_store)):
    try:
        return store.save_annotation(a.model_dump())
    except AnnotationError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/export")
def export(batch_id: str, format: str = Query("jsonl", pattern="^(jsonl|csv)$"), store=Depends(get_store)):
    import json

    if format == "csv":
        return PlainTextResponse(store.export_csv(batch_id), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{batch_id}.csv"'})
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in store.export(batch_id))
    return PlainTextResponse(body, media_type="application/x-ndjson",
                             headers={"Content-Disposition": f'attachment; filename="{batch_id}.jsonl"'})
