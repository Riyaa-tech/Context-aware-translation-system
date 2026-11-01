"""Validate challenge-set JSONL files against the schema in docs/DATASET_GUIDE.md.

Usage: python scripts/validate_dataset.py file1.jsonl [file2.jsonl ...]
Exit code 1 if any error is found.
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.experiments.datasets import load_challenge_files  # noqa: E402


def main(paths):
    ds = load_challenge_files(paths, ROOT)
    for f in ds.files:
        print(f"{f['path']}: {f['n_rows']} rows, sha256 {f['sha256'][:12]}")
    print("by split:", dict(Counter(r.get("split") for r in ds.rows)))
    print("by category:", dict(Counter(r.get("category") for r in ds.rows)))
    print("by direction:", dict(Counter(f"{r.get('source_language')}->{r.get('target_language')}" for r in ds.rows)))
    small = [k for k, v in Counter((r.get("category"), r.get("source_language")) for r in ds.rows).items() if v < 10]
    if small:
        print(f"note: {len(small)} category/language cells have < 10 items (flag as small in reports)")
    if ds.errors:
        print(f"\n{len(ds.errors)} ERROR(S):")
        for e in ds.errors:
            print("  " + e)
        sys.exit(1)
    print("OK: no errors")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
