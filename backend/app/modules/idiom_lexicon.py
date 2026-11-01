"""Load, validate and compile the JSON idiom lexicon."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.modules.text_utils import LEFT_BOUNDARY, RIGHT_BOUNDARY

DEFAULT_LEXICON = Path(__file__).resolve().parents[2] / "resources" / "idioms" / "lexicon.json"

REQUIRED_FIELDS = [
    "idiom_id", "expression", "source_language", "intended_meaning", "literal_meaning",
    "example_context", "provenance", "confidence", "review_status", "forms",
]
REVIEW_STATUSES = {"draft", "reviewed", "rejected"}

# Possessive slot: "pulling {poss} leg" -> group "poss"; paraphrase may use {poss} or {obj}.
POSS_PATTERN = r"(?P<poss>my|your|his|her|our|their|its|[A-Za-z]+'s)"
POSS_TO_OBJ = {"my": "me", "your": "you", "his": "him", "her": "her", "our": "us", "their": "them", "its": "it"}


def poss_to_obj(poss: str) -> str:
    p = poss.lower()
    if p in POSS_TO_OBJ:
        return POSS_TO_OBJ[p] if poss[0].islower() else POSS_TO_OBJ[p].capitalize()
    return poss[:-2] if poss.endswith("'s") else poss


@dataclass
class IdiomForm:
    surface: str
    paraphrase: str
    regex: re.Pattern


@dataclass
class IdiomEntry:
    idiom_id: str
    expression: str
    source_language: str
    intended_meaning: str
    literal_meaning: str
    example_context: str
    provenance: str
    confidence: float
    review_status: str
    forms: list[IdiomForm]
    figurative_cues: list[str] = field(default_factory=list)
    literal_cues: list[str] = field(default_factory=list)
    literal_followers: list[str] = field(default_factory=list)
    figurative_prior: float = 0.75
    notes: str | None = None

    def public_dict(self) -> dict:
        return {
            "idiom_id": self.idiom_id, "expression": self.expression, "source_language": self.source_language,
            "intended_meaning": self.intended_meaning, "literal_meaning": self.literal_meaning,
            "example_context": self.example_context, "provenance": self.provenance,
            "confidence": self.confidence, "review_status": self.review_status,
            "forms": [{"surface": f.surface, "paraphrase": f.paraphrase} for f in self.forms],
            "figurative_cues": self.figurative_cues, "literal_cues": self.literal_cues,
            "literal_followers": self.literal_followers, "figurative_prior": self.figurative_prior,
            "notes": self.notes,
        }


class LexiconError(ValueError):
    pass


def _compile_surface(surface: str) -> re.Pattern:
    parts = re.split(r"(\{poss\})", surface)
    out = []
    for p in parts:
        if p == "{poss}":
            out.append(POSS_PATTERN)
        else:
            # allow any run of whitespace between words
            out.append(r"\s+".join(re.escape(w) for w in p.split(" ")) if p.strip() else re.escape(p).replace(r"\ ", r"\s+"))
    pattern = "".join(out).replace(r"\s+\s+", r"\s+")
    return re.compile(LEFT_BOUNDARY + pattern + RIGHT_BOUNDARY, re.IGNORECASE)


def _validate(raw: dict, seen: set[str]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise LexiconError(f"{raw.get('idiom_id', '?')}: missing fields {missing}")
    if raw["idiom_id"] in seen:
        raise LexiconError(f"duplicate idiom_id {raw['idiom_id']}")
    if raw["review_status"] not in REVIEW_STATUSES:
        raise LexiconError(f"{raw['idiom_id']}: review_status must be one of {REVIEW_STATUSES}")
    if not 0.0 <= float(raw["confidence"]) <= 1.0:
        raise LexiconError(f"{raw['idiom_id']}: confidence must be in [0, 1]")
    if not raw["forms"]:
        raise LexiconError(f"{raw['idiom_id']}: needs at least one form")
    for f in raw["forms"]:
        has_slot = "{poss}" in f["surface"]
        uses_slot = "{poss}" in f["paraphrase"] or "{obj}" in f["paraphrase"]
        if uses_slot and not has_slot:
            raise LexiconError(f"{raw['idiom_id']}: paraphrase uses a slot that the surface does not define")


def load_lexicon_from_dict(doc: dict) -> list[IdiomEntry]:
    entries: list[IdiomEntry] = []
    seen: set[str] = set()
    for raw in doc["entries"]:
        _validate(raw, seen)
        seen.add(raw["idiom_id"])
        forms = [IdiomForm(f["surface"], f["paraphrase"], _compile_surface(f["surface"])) for f in raw["forms"]]
        entries.append(
            IdiomEntry(
                idiom_id=raw["idiom_id"], expression=raw["expression"], source_language=raw["source_language"],
                intended_meaning=raw["intended_meaning"], literal_meaning=raw["literal_meaning"],
                example_context=raw["example_context"], provenance=raw["provenance"],
                confidence=float(raw["confidence"]), review_status=raw["review_status"], forms=forms,
                figurative_cues=raw.get("figurative_cues", []), literal_cues=raw.get("literal_cues", []),
                literal_followers=raw.get("literal_followers", []),
                figurative_prior=float(raw.get("figurative_prior", 0.75)), notes=raw.get("notes"),
            )
        )
    return entries


@lru_cache(maxsize=4)
def load_lexicon(path: str | None = None) -> tuple[dict, list[IdiomEntry]]:
    p = Path(path) if path else DEFAULT_LEXICON
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in doc.items() if k != "entries"}, load_lexicon_from_dict(doc)
