"""Research metrics computed from stored runs (+ human ratings when available). Nothing is simulated."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_store
from app.evaluation.report import evaluate_run
from app.experiments.runner import ExperimentError, list_runs

router = APIRouter(prefix="/api/research", tags=["research"])


def _pick(exp_id: str | None) -> str:
    if exp_id:
        return exp_id
    done = [r for r in list_runs() if r["status"] == "complete"]
    if not done:
        raise HTTPException(404, "no completed experiment runs")
    return done[0]["experiment_id"]


@router.get("/metrics")
def metrics(experiment_id: str | None = None, batch_id: str | None = None, store=Depends(get_store)):
    try:
        return evaluate_run(_pick(experiment_id), store=store, batch_id=batch_id, bootstrap_samples=300)
    except (ExperimentError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


@router.get("/ablation")
def ablation(experiment_id: str | None = None, batch_id: str | None = None, store=Depends(get_store)):
    """Compact table: one row per condition. Unavailable values are null with a reason, never 0."""
    rep = metrics(experiment_id, batch_id, store)
    sem = rep["semantic"]
    rows = []
    for c, label in rep["conditions"].items():
        gq = rep["general_quality"].get(c, {})
        s = sem["per_condition"].get(c) if sem.get("available") else None
        cats = (s or {}).get("by_category", {})
        rows.append({
            "condition": c, "label": label,
            "bleu_13a": _dir_scores(gq, "bleu_13a"), "spbleu_flores200": _dir_scores(gq, "spbleu_flores200"),
            "chrfpp": _dir_scores(gq, "chrfpp"),
            "spr_overall": s["overall"]["spr"] if s else None,
            "spr_idiom": cats.get("idiom", {}).get("spr"), "spr_sarcasm": cats.get("sarcasm", {}).get("spr"),
            "spr_context": cats.get("context", {}).get("spr"),
            "delta_spr_pp": (s or {}).get("delta_vs_A", {}).get("overall", {}).get("delta_pp"),
            "intervention_coverage": rep["controller"][c]["intervention_coverage"],
            "harmful_intervention_rate": (s or {}).get("harmful_intervention", {}).get("harmful_intervention_rate"),
            "latency_ms": rep["latency"].get(c),
        })
    return {"experiment_id": rep["experiment_id"], "reportable": rep["reportable"], "notes": rep["notes"],
            "semantic_available": sem.get("available", False), "semantic_reason": sem.get("reason"), "rows": rows}


def _dir_scores(gq: dict, name: str):
    if not gq or gq.get("available") is False:
        return None
    return {d: v[name]["score"] for d, v in gq["by_direction"].items()}
