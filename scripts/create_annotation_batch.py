"""Create a blinded annotation batch from a completed run.

  python scripts/create_annotation_batch.py <experiment_id> [--conditions A,B_paraphrase] [--categories idiom,context]
Then raters open http://localhost:8000/annotate (React app) or /annotate-lite.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.annotation.store import DEFAULT_DB, AnnotationStore  # noqa: E402
from app.experiments.runner import read_predictions, read_run  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("experiment_id")
ap.add_argument("--conditions")
ap.add_argument("--categories")
ap.add_argument("--seed", type=int, default=20261101)
a = ap.parse_args()
m = read_run(a.experiment_id)
conds = a.conditions.split(",") if a.conditions else [c for c, s in m["conditions"].items() if s["status"] == "complete"]
preds = {c: read_predictions(a.experiment_id, c) for c in conds}
b = AnnotationStore(os.getenv("ANNOTATION_DB", str(DEFAULT_DB))).create_batch(a.experiment_id, preds, seed=a.seed,
                                             categories=a.categories.split(",") if a.categories else None)
print(f"batch {b['batch_id']}: {b['n_items']} items to rate (from {b['n_condition_outputs']} condition outputs; "
      f"identical outputs merged); conditions {b['conditions']}")
if not m["reportable"]:
    print("NOTE: this run is a DEV run - ratings are for piloting the annotation protocol, not for reporting.")
