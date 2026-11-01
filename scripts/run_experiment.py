"""Run or resume an experiment.

  python scripts/run_experiment.py experiments/configs/pilot_dev.yaml
  python scripts/run_experiment.py --resume <experiment_id>
  python scripts/run_experiment.py --list
"""
import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.deps import get_engine  # noqa: E402
from app.experiments.runner import ExperimentRunner, list_runs, load_config  # noqa: E402

logging.basicConfig(level=logging.WARNING)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?")
    ap.add_argument("--resume")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for r in list_runs():
            print(f"{r['experiment_id']}  {r['status']:12s} split={r['split']}  n={r['n_examples']}  {r['conditions']}")
        return
    runner = ExperimentRunner(get_engine())
    if a.resume:
        exp_id = a.resume
    elif a.config:
        exp_id = runner.create(load_config(a.config))
        print(f"created {exp_id}")
    else:
        ap.error("give a config file or --resume <experiment_id>")
    m = runner.run(exp_id)
    print(f"status: {m['status']}")
    for c, s in m["conditions"].items():
        print(f"  {c:14s} {s['status']:9s} done={s['done']} errors={s['errors']} wall={s.get('wall_seconds')}s "
              f"decisions={s.get('decision_counts')} latency={s.get('latency_ms')}")
    if "consistency" in m:
        print("same example IDs across conditions:", m["consistency"]["ok"])
    print(f"results in experiments/runs/{exp_id}/")


if __name__ == "__main__":
    main()
