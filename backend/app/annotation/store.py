"""SQLite annotation store with blinded batches.

A batch is built from one experiment run. For each example, every distinct final translation across
the selected conditions becomes ONE item (identical outputs are rated once). The item -> condition
mapping is stored separately and never served to raters. Ratings are only ever entered by people.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.annotation.rubric import ERROR_CATEGORIES, RATINGS, SUB_SCALE

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "experiments" / "annotations" / "annotations.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
  batch_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, created_at TEXT NOT NULL, seed INTEGER NOT NULL,
  conditions TEXT NOT NULL, categories TEXT, n_items INTEGER NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS items (
  item_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, example_id TEXT NOT NULL, translation TEXT NOT NULL,
  source_text TEXT NOT NULL, context TEXT NOT NULL, intended_meaning TEXT, reference_translation TEXT,
  source_lang TEXT NOT NULL, target_lang TEXT NOT NULL, category TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS item_sources (item_id TEXT NOT NULL, condition TEXT NOT NULL, PRIMARY KEY (item_id, condition));
CREATE TABLE IF NOT EXISTS annotations (
  annotation_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, rater_id TEXT NOT NULL,
  rating TEXT NOT NULL, core_proposition TEXT, figurative_meaning TEXT, pragmatic_intent TEXT,
  unsupported_addition INTEGER, omission INTEGER, primary_error TEXT, secondary_errors TEXT, comment TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE (item_id, rater_id));
CREATE TABLE IF NOT EXISTS annotation_history (
  item_id TEXT NOT NULL, rater_id TEXT NOT NULL, payload TEXT NOT NULL, saved_at TEXT NOT NULL);
"""


class AnnotationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnnotationStore:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # ---------- batches ----------
    def create_batch(self, experiment_id: str, predictions: dict[str, list[dict]], seed: int = 20261101,
                     categories: list[str] | None = None, note: str = "") -> dict:
        """predictions: {condition: [records]} from one run."""
        conds = sorted(predictions)
        batch_id = f"{experiment_id}__b{hashlib.sha1(json.dumps([conds, categories, seed]).encode()).hexdigest()[:8]}"
        items: dict[str, dict] = {}
        sources: set[tuple[str, str]] = set()
        for cond, recs in predictions.items():
            for r in recs:
                if categories and r["category"] not in categories:
                    continue
                if r.get("translation_status") == "error":
                    continue  # failed outputs are reported by the runner; nothing to rate
                iid = hashlib.sha1(f"{batch_id}|{r['example_id']}|{r['final_translation']}".encode()).hexdigest()[:16]
                items.setdefault(iid, {
                    "item_id": iid, "example_id": r["example_id"], "translation": r["final_translation"],
                    "source_text": r["original_sentence"], "context": json.dumps(r.get("context", []), ensure_ascii=False),
                    "intended_meaning": r.get("intended_meaning"), "reference_translation": r.get("reference_translation"),
                    "source_lang": r["source_lang"], "target_lang": r["target_lang"], "category": r["category"]})
                sources.add((iid, cond))
        with self._lock, self._conn() as c:
            if c.execute("SELECT 1 FROM batches WHERE batch_id=?", (batch_id,)).fetchone():
                raise AnnotationError(f"batch {batch_id} already exists")
            c.execute("INSERT INTO batches VALUES (?,?,?,?,?,?,?,?)",
                      (batch_id, experiment_id, _now(), seed, json.dumps(conds), json.dumps(categories), len(items), note))
            c.executemany("INSERT INTO items VALUES (:item_id,:batch_id,:example_id,:translation,:source_text,:context,"
                          ":intended_meaning,:reference_translation,:source_lang,:target_lang,:category)",
                          [{**v, "batch_id": batch_id} for v in items.values()])
            c.executemany("INSERT INTO item_sources VALUES (?,?)", sorted(sources))
        n_outputs = sum(len(v) for v in predictions.values())
        return {"batch_id": batch_id, "n_items": len(items), "n_condition_outputs": n_outputs, "conditions": conds}

    def list_batches(self) -> list[dict]:
        with self._conn() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM batches ORDER BY created_at DESC")]
            for r in rows:
                r["conditions"] = json.loads(r["conditions"])
                r["categories"] = json.loads(r["categories"]) if r["categories"] else None
                r["raters"] = {x["rater_id"]: x["n"] for x in c.execute(
                    "SELECT a.rater_id, COUNT(*) n FROM annotations a JOIN items i USING(item_id) WHERE i.batch_id=? "
                    "GROUP BY a.rater_id", (r["batch_id"],))}
        return rows

    # ---------- rater view (blinded) ----------
    def rater_items(self, batch_id: str, rater_id: str, only_pending: bool = False) -> dict:
        _check_rater(rater_id)
        with self._conn() as c:
            b = c.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
            if not b:
                raise AnnotationError(f"unknown batch {batch_id}")
            rows = [dict(r) for r in c.execute(
                "SELECT item_id, source_text, context, intended_meaning, reference_translation, source_lang, target_lang, "
                "translation FROM items WHERE batch_id=? ORDER BY item_id", (batch_id,))]
            done = {r["item_id"]: dict(r) for r in c.execute(
                "SELECT a.* FROM annotations a JOIN items i USING(item_id) WHERE i.batch_id=? AND a.rater_id=?", (batch_id, rater_id))}
        # Per-rater deterministic shuffle so raters see different orders and cannot infer systems from position.
        random.Random(f"{b['seed']}|{rater_id}").shuffle(rows)
        for r in rows:
            r["context"] = json.loads(r["context"])
            r["my_annotation"] = _clean_annotation(done.get(r["item_id"]))
        if only_pending:
            rows = [r for r in rows if r["my_annotation"] is None]
        return {"batch_id": batch_id, "rater_id": rater_id, "total": b["n_items"], "done": len(done), "items": rows}

    def save_annotation(self, a: dict) -> dict:
        _check_rater(a.get("rater_id", ""))
        if a.get("rating") not in RATINGS:
            raise AnnotationError(f"rating must be one of {list(RATINGS)}")
        for k in ("core_proposition", "figurative_meaning", "pragmatic_intent"):
            if a.get(k) not in (None, *SUB_SCALE):
                raise AnnotationError(f"{k} must be one of {SUB_SCALE}")
        errs = [a.get("primary_error")] + list(a.get("secondary_errors") or [])
        bad = [e for e in errs if e is not None and e not in ERROR_CATEGORIES]
        if bad:
            raise AnnotationError(f"unknown error categories {bad}")
        now = _now()
        with self._lock, self._conn() as c:
            if not c.execute("SELECT 1 FROM items WHERE item_id=?", (a["item_id"],)).fetchone():
                raise AnnotationError(f"unknown item {a['item_id']}")
            c.execute(
                "INSERT INTO annotations (item_id, rater_id, rating, core_proposition, figurative_meaning, pragmatic_intent, "
                "unsupported_addition, omission, primary_error, secondary_errors, comment, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_id, rater_id) DO UPDATE SET rating=excluded.rating, "
                "core_proposition=excluded.core_proposition, figurative_meaning=excluded.figurative_meaning, "
                "pragmatic_intent=excluded.pragmatic_intent, unsupported_addition=excluded.unsupported_addition, "
                "omission=excluded.omission, primary_error=excluded.primary_error, secondary_errors=excluded.secondary_errors, "
                "comment=excluded.comment, updated_at=excluded.updated_at",
                (a["item_id"], a["rater_id"], a["rating"], a.get("core_proposition"), a.get("figurative_meaning"),
                 a.get("pragmatic_intent"), _bool(a.get("unsupported_addition")), _bool(a.get("omission")),
                 a.get("primary_error"), json.dumps(a.get("secondary_errors") or []), a.get("comment"), now, now))
            c.execute("INSERT INTO annotation_history VALUES (?,?,?,?)",
                      (a["item_id"], a["rater_id"], json.dumps(a, ensure_ascii=False), now))
        return {"saved": True, "item_id": a["item_id"], "rater_id": a["rater_id"]}

    # ---------- analysis view (unblinded) ----------
    def export(self, batch_id: str) -> list[dict]:
        """One row per (item, rater) with the conditions that produced the item."""
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT i.*, a.rater_id, a.rating, a.core_proposition, a.figurative_meaning, a.pragmatic_intent, "
                "a.unsupported_addition, a.omission, a.primary_error, a.secondary_errors, a.comment, a.updated_at "
                "FROM items i JOIN annotations a USING(item_id) WHERE i.batch_id=? ORDER BY i.example_id, a.rater_id", (batch_id,))]
            src: dict[str, list[str]] = {}
            for r in c.execute("SELECT s.item_id, s.condition FROM item_sources s JOIN items i USING(item_id) WHERE i.batch_id=?",
                               (batch_id,)):
                src.setdefault(r["item_id"], []).append(r["condition"])
        for r in rows:
            r["conditions"] = sorted(src.get(r["item_id"], []))
            r["context"] = json.loads(r["context"])
            r["secondary_errors"] = json.loads(r["secondary_errors"] or "[]")
        return rows

    def export_csv(self, batch_id: str) -> str:
        rows = self.export(batch_id)
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0]))
            w.writeheader()
            for r in rows:
                w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in r.items()})
        return buf.getvalue()

    def ratings_for(self, batch_id: str) -> dict[tuple[str, str], dict[str, str]]:
        """{(example_id, translation): {rater_id: rating}}"""
        out: dict[tuple[str, str], dict[str, str]] = {}
        for r in self.export(batch_id):
            out.setdefault((r["example_id"], r["translation"]), {})[r["rater_id"]] = r["rating"]
        return out


def _check_rater(rater_id: str) -> None:
    if not rater_id or not rater_id.replace("_", "").replace("-", "").isalnum() or len(rater_id) > 40:
        raise AnnotationError("rater_id must be 1-40 letters, digits, '-' or '_'")


def _bool(v):
    return None if v is None else int(bool(v))


def _clean_annotation(a: dict | None) -> dict | None:
    if not a:
        return None
    a = {k: a[k] for k in ("rating", "core_proposition", "figurative_meaning", "pragmatic_intent", "unsupported_addition",
                           "omission", "primary_error", "secondary_errors", "comment", "updated_at")}
    a["secondary_errors"] = json.loads(a["secondary_errors"] or "[]")
    return a
