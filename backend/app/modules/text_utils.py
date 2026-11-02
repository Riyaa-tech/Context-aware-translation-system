"""Small text helpers shared by the semantic modules."""
from __future__ import annotations

import re
import unicodedata

# Characters treated as "inside a word" for boundary checks. Python's \w misses Devanagari
# vowel signs (category Mc/Mn), so they are added explicitly.
WORD_CHARS = r"\w\u0900-\u0963\u0966-\u097F"  # excludes the dandas । (U+0964) and ॥ (U+0965)
LEFT_BOUNDARY = rf"(?<![{WORD_CHARS}])"
RIGHT_BOUNDARY = rf"(?![{WORD_CHARS}])"
TOKEN_RE = re.compile(rf"[{WORD_CHARS}']+")

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def normalize_same_length(text: str) -> str:
    """NFC-normalize and straighten apostrophes. Keeps length the same so match
    offsets remain valid on the original string (NFC is applied only if it does not change length)."""
    nfc = unicodedata.normalize("NFC", text)
    base = nfc if len(nfc) == len(text) else text
    return base.translate(_APOSTROPHES)


def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(normalize_same_length(text))]


def cue_matches(cue: str, toks: list[str], joined: str) -> bool:
    """A cue matches a token by prefix (for cues of 4+ chars, to cover inflections like
    cook -> cooking) or exactly. Multi-word cues match as a substring of the joined tokens."""
    cue = cue.lower().strip()
    if " " in cue:
        return f" {cue} " in f" {joined} "
    if len(cue) >= 4:
        return any(t.startswith(cue) for t in toks)
    # Short cues match exactly or with a plural ending (egg -> eggs). Added after a dev-set error.
    return any(t in (cue, cue + "s", cue + "es") for t in toks)


_SENTENCE_OPENERS = set(".!?\u0964\"\u201e\u201c\u00ab(")


def at_sentence_start(text: str, start: int) -> bool:
    """True if `start` is the first word of a sentence (only spaces/quotes after . ! ? or the danda)."""
    before = text[:start].rstrip()
    return before == "" or before[-1] in _SENTENCE_OPENERS


def case_for_position(template: str, text: str, start: int) -> str:
    """Capitalise the replacement only at a sentence start. Otherwise keep the template's own
    casing, so German nouns stay capitalised and nothing else is (an uppercase German noun
    mid-sentence must not capitalise the paraphrase)."""
    if template and at_sentence_start(text, start):
        return template[0].upper() + template[1:]
    return template
