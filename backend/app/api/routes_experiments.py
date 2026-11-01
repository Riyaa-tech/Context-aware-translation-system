"""Experiment endpoints. Runs execute in one background thread (one run at a time)."""
from __future__ import annotations

import threading
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_engine
from app.experiments.conditions import ConditionError, list_conditions
from app.experiments.datasets import DatasetError
from app.experiments.runner import ExperimentError, ExperimentRunner, list_runs, load_config, read_predictions, read_run

router = APIRouter(prefix="/api/experiments", tags=["experiments"])
_lock = threading.Lock()
_active: dict = {"experiment_id": None, "error": None}


class RunRequest(BaseModel):
    config_file: str | None = None  # path under experiments/configs/
    resume_experiment_id: str | None = None


def _background(runner: ExperimentRunner, exp_id: str):
    try:
        runner.run(exp_id)
    except Exception as e:  # recorded in the manifest by the runner as well
        _active["error"] = f"{type(e).__name__}: {e}"
    finally:
        _active["experiment_id"] = None
        _lock.release()


@router.get("/conditions")
def conditions():
    return {"conditions": list_conditions()}


@router.post("/run", status_code=202)
def run(req: RunRequest, engine=Depends(get_engine)):
    if not (req.config_file or req.resume_experiment_id):
        raise HTTPException(422, "give config_file or resume_experiment_id")
    if req.config_file and (".." in req.config_file or not req.config_file.startswith("experiments/configs/")):
        raise HTTPException(400, "config_file must be inside experiments/configs/")
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, f"experiment {_active['experiment_id']} is already running")
    try:
        runner = ExperimentRunner(engine)
        exp_id = req.resume_experiment_id or runner.create(load_config(req.config_file))
        read_run(exp_id)
    except (ExperimentError, ConditionError, DatasetError, FileNotFoundError) as e:
        _lock.release()
        raise HTTPException(400, str(e)) from e
    except Exception:
        _lock.release()
        raise
    _active.update({"experiment_id": exp_id, "error": None})
    threading.Thread(target=_background, args=(runner, exp_id), daemon=True).start()
    return {"experiment_id": exp_id, "status": "started"}


@router.get("")
def experiments():
    return {"active": _active, "experiments": list_runs()}


@router.get("/{experiment_id}")
def experiment(experiment_id: str):
    try:
        m = read_run(experiment_id)
    except ExperimentError as e:
        raise HTTPException(404, str(e)) from e
    m = dict(m)
    m["example_ids"] = f"{len(m['example_ids'])} ids (see manifest.json)"
    return m


@router.get("/{experiment_id}/results")
def results(experiment_id: str, include_records: bool = False):
    """Per-condition summaries of stored predictions. Quality metrics (BLEU/chrF++/SPR) come from the
    evaluation module and human annotations; they are NOT computed here."""
    try:
        m = read_run(experiment_id)
    except ExperimentError as e:
        raise HTTPException(404, str(e)) from e
    out = {}
    for cond, state in m["conditions"].items():
        try:
            recs = read_predictions(experiment_id, cond)
        except ExperimentError:
            out[cond] = {"status": state["status"], "n": 0}
            continue
        by_cat = {}
        for r in recs:
            c = by_cat.setdefault(r["category"], Counter())
            c[r["controller_decision"]] += 1
        out[cond] = {
            "status": state["status"], "label": state["label"], "n": len(recs),
            "decision_counts": dict(Counter(r["controller_decision"] for r in recs)),
            "decisions_by_category": {k: dict(v) for k, v in by_cat.items()},
            "translation_status": dict(Counter(r["translation_status"] for r in recs)),
            "intervention_coverage": sum(r["controller_decision"] == "INTERVENE" for r in recs) / len(recs) if recs else None,
            "latency_ms": state.get("latency_ms"),
            **({"records": recs} if include_records else {}),
        }
    return {"experiment_id": experiment_id, "status": m["status"], "reportable": m["reportable"],
            "metrics_note": "BLEU, chrF++ and SPR are not computed here (Milestone 5).", "conditions": out}
