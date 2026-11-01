"""Challenge-set loading, validation, versioning and reproducible splitting."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.config.languages import LANGUAGES

REQUIRED = ["example_id", "source_language", "target_language", "category", "source_text", "context",
            "intended_meaning", "reference_translation", "provenance", "split"]
CATEGORIES = {
    "idiom", "idiom_literal_control", "no_idiom_control",
    "sarcasm", "sincere_control",
    "context", "context_irrelevant_control", "context_missing_control", "context_independent_control",
    "context_ambiguous_control", "no_ambiguity_control", "pronoun_reference",
}
SPLITS = {"dev", "test", "unassigned"}


class DatasetError(ValueError):
    pass


@dataclass
class LoadedDataset:
    rows: list[dict]
    files: list[dict]  # [{path, sha256, n_rows}]
    errors: list[str]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_row(r: dict, line: int, path: str) -> list[str]:
    errs = []
    where = f"{path}:{line} ({r.get('example_id', '?')})"
    missing = [k for k in REQUIRED if k not in r]
    if missing:
        return [f"{where}: missing fields {missing}"]
    if r["source_language"] not in LANGUAGES or r["target_language"] not in LANGUAGES:
        errs.append(f"{where}: unknown language code")
    if r["source_language"] == r["target_language"]:
        errs.append(f"{where}: source and target language are the same")
    if r["category"] not in CATEGORIES:
        errs.append(f"{where}: unknown category '{r['category']}'")
    if r["split"] not in SPLITS:
        errs.append(f"{where}: split must be one of {sorted(SPLITS)}")
    if not isinstance(r["context"], list):
        errs.append(f"{where}: context must be a list of sentences")
    if not str(r["source_text"]).strip():
        errs.append(f"{where}: empty source_text")
    if not str(r["provenance"]).strip():
        errs.append(f"{where}: provenance is required")
    return errs


def load_challenge_files(paths: list[str | Path], root: Path | None = None) -> LoadedDataset:
    rows, files, errors, seen = [], [], [], {}
    for p in paths:
        path = Path(p)
        if root and not path.is_absolute():
            path = root / path
        if not path.exists():
            raise DatasetError(f"dataset file not found: {path}")
        n = 0
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{path}:{i}: invalid JSON ({e})")
                continue
            errors += validate_row(r, i, str(path))
            if r.get("example_id") in seen:
                errors.append(f"{path}:{i}: duplicate example_id {r['example_id']} (first in {seen[r['example_id']]})")
            seen[r.get("example_id")] = str(path)
            rows.append(r)
            n += 1
        rel = str(path.relative_to(root)) if root and path.is_relative_to(root) else str(path)
        files.append({"path": rel, "sha256": file_sha256(path), "n_rows": n})
    texts = {}
    for r in rows:  # exact duplicates (paper IV-D: remove exact duplicates)
        key = (r.get("source_language"), r.get("source_text"), tuple(r.get("context") or []))
        if key in texts:
            errors.append(f"exact duplicate source+context: {texts[key]} and {r.get('example_id')}")
        texts[key] = r.get("example_id")
    return LoadedDataset(rows, files, errors)


def assign_split(example_id: str, seed: int, test_fraction: float) -> str:
    """Deterministic, order-independent split from a hash of (seed, example_id)."""
    h = int(hashlib.sha256(f"{seed}:{example_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if h < test_fraction else "dev"
