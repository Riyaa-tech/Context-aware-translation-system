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
OPTIONAL_METADATA = ("english_equivalent", "supported_directions", "source_reference")

# Slots usable in lexicon surface forms (each becomes a named regex group the paraphrase may reuse):
#   {poss}  English possessive: "pulling {poss} leg" -> paraphrase may use {poss} or {obj}
#   {akk}   German accusative object: pronoun, or determiner + up to 2 words ("das Kind", "seinen neuen Chef")
#   {dat}   German dative object: pronoun, or determiner + up to 2 words ("mir", "meiner Schwester")
#   {gap2}  a second gap of up to 2 words (e.g. the subject after a fronted verb)
#   {gap}   up to 2 extra words (German word order: "hast wohl Tomaten ...", "nimmst mich schon wieder ...");
#           the captured text keeps its leading space, so write it attached in paraphrases: "übersiehst{gap} das ..."
POSS_PATTERN = r"(?P<poss>my|your|his|her|our|their|its|[A-Za-z]+'s)"
_DE_DET_AKK = "den|die|das|einen|eine|ein|meinen|deinen|seinen|ihren|unseren|euren|meine|deine|seine|ihre|unsere|eure|mein|dein|sein"
_DE_DET_DAT = "dem|der|einem|einer|meinem|meiner|deinem|deiner|seinem|seiner|ihrem|ihrer|unserem|unserer|eurem|eurer"
AKK_PATTERN = rf"(?P<akk>mich|dich|ihn|sie|es|uns|euch|(?:{_DE_DET_AKK})(?:\s+\w+){{1,2}})"
DAT_PATTERN = rf"(?P<dat>mir|dir|ihm|ihr|uns|euch|ihnen|(?:{_DE_DET_DAT})(?:\s+\w+){{1,2}})"
GAP_PATTERN = r"(?P<gap>(?:\s+[^\s.,;:!?]+){0,2}?)"
GAP2_PATTERN = r"(?P<gap2>(?:\s+[^\s.,;:!?]+){0,2}?)"  # second gap, e.g. a subject after the verb: "drückst du mir ..."
SLOT_PATTERNS = {"poss": POSS_PATTERN, "akk": AKK_PATTERN, "dat": DAT_PATTERN}
_SLOT_RE = re.compile(r"(\{(?:poss|akk|dat|gap2|gap)\})")
SLOT_VALUE_NAMES = ("akk", "dat")  # slot text that also counts as evidence for literal/figurative cues
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
    extra: dict = field(default_factory=dict)  # optional metadata, e.g. english_equivalent, supported_directions, source_reference

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
            **self.extra,
        }


class LexiconError(ValueError):
    pass


def _compile_surface(surface: str) -> re.Pattern:
    """Words are joined by any run of whitespace; {gap} carries its own leading whitespace."""
    out: list[str] = []
    for i, token in enumerate(surface.split()):
        atoms = [a for a in _SLOT_RE.split(token) if a]
        for j, atom in enumerate(atoms):
            if atom in ("{gap}", "{gap2}"):
                out.append(GAP_PATTERN if atom == "{gap}" else GAP2_PATTERN)
                continue
            if i > 0 and j == 0:
                out.append(r"\s+")
            out.append(SLOT_PATTERNS[atom[1:-1]] if atom.startswith("{") and atom[1:-1] in SLOT_PATTERNS else re.escape(atom))
    return re.compile(LEFT_BOUNDARY + "".join(out) + RIGHT_BOUNDARY, re.IGNORECASE)


def slots_in(text: str) -> set[str]:
    found = {m[1:-1] for m in _SLOT_RE.findall(text)} | ({"poss"} if "{obj}" in text else set())
    return found


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
        missing_slots = slots_in(f["paraphrase"]) - slots_in(f["surface"])
        if missing_slots:
            raise LexiconError(f"{raw['idiom_id']}: paraphrase uses a slot that the surface does not define {sorted(missing_slots)}")
        if "{poss}" in f["surface"] and ("{akk}" in f["surface"] or "{dat}" in f["surface"]):
            raise LexiconError(f"{raw['idiom_id']}: do not mix English and German slots in one form")


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
                extra={k: raw[k] for k in OPTIONAL_METADATA if k in raw},
            )
        )
    return entries


@lru_cache(maxsize=4)
def load_lexicon(path: str | None = None) -> tuple[dict, list[IdiomEntry]]:
    p = Path(path) if path else DEFAULT_LEXICON
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in doc.items() if k != "entries"}, load_lexicon_from_dict(doc)
