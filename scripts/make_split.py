"""Assign dev/test splits reproducibly (hash of seed + example_id; independent of row order).

Usage: python scripts/make_split.py pool.jsonl out.jsonl --seed 20261101 --test-fraction 0.8
Rows that already have split 'dev' or 'test' keep it unless --force is given.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.experiments.datasets import assign_split  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("pool")
ap.add_argument("out")
ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--test-fraction", type=float, default=0.8)
ap.add_argument("--force", action="store_true")
a = ap.parse_args()
if Path(a.out).exists():
    sys.exit(f"{a.out} exists; refusing to overwrite")
rows = [json.loads(l) for l in open(a.pool, encoding="utf-8") if l.strip()]
for r in rows:
    if a.force or r.get("split") not in ("dev", "test"):
        r["split"] = assign_split(r["example_id"], a.seed, a.test_fraction)
        r["split_seed"] = a.seed
with open(a.out, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print({s: sum(r["split"] == s for r in rows) for s in ("dev", "test")}, f"seed={a.seed}")
