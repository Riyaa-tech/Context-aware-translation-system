"""Load the ambiguous-word sense inventory used by the context module."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.modules.text_utils import LEFT_BOUNDARY, RIGHT_BOUNDARY

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "resources" / "senses" / "sense_inventory.json"


@dataclass
class Sense:
    sense_id: str
    gloss: str
    cues: list[str]
    replacements: dict[str, str]


@dataclass
class AmbiguousWord:
    word_id: str
    lemma: str
    source_language: str
    forms: list[str]
    senses: list[Sense]
    regex: re.Pattern


class InventoryError(ValueError):
    pass


def load_inventory_from_dict(doc: dict) -> list[AmbiguousWord]:
    words, seen = [], set()
    for w in doc["words"]:
        if w["word_id"] in seen:
            raise InventoryError(f"duplicate word_id {w['word_id']}")
        seen.add(w["word_id"])
        if len(w["senses"]) < 2:
            raise InventoryError(f"{w['word_id']}: an ambiguous word needs at least two senses")
        senses = []
        for s in w["senses"]:
            missing = [f for f in w["forms"] if f not in s["replacements"]]
            if missing:
                raise InventoryError(f"{s['sense_id']}: no replacement for forms {missing}")
            senses.append(Sense(s["sense_id"], s["gloss"], s["cues"], s["replacements"]))
        forms = sorted(w["forms"], key=len, reverse=True)
        regex = re.compile(LEFT_BOUNDARY + "(" + "|".join(re.escape(f) for f in forms) + ")" + RIGHT_BOUNDARY, re.IGNORECASE)
        words.append(AmbiguousWord(w["word_id"], w["lemma"], w["source_language"], w["forms"], senses, regex))
    return words


@lru_cache(maxsize=4)
def load_inventory(path: str | None = None) -> tuple[dict, list[AmbiguousWord]]:
    p = Path(path) if path else DEFAULT_INVENTORY
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in doc.items() if k != "words"}, load_inventory_from_dict(doc)
