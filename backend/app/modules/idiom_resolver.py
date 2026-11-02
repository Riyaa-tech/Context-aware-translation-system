"""M1 step 3: turn accepted idiom candidates into rewrites of the NLLB input.

Modes (compared in the experiment, paper Section IV-E):
  hint        -> keep the idiom and add its meaning in brackets: "spilled the beans (revealed the secret)"
  paraphrase  -> replace the idiom with its controlled paraphrase: "revealed the secret"
"""
from __future__ import annotations

from app.modules.idiom_detector import IdiomCandidate
from app.modules.rewrite import Rewrite, apply_rewrites
from app.modules.text_utils import case_for_position

IDIOM_MODES = ("hint", "paraphrase")
HINT_TEMPLATE = "{span} ({gloss})"


def idiom_rewrites(text: str, accepted: list[IdiomCandidate], mode: str) -> list[Rewrite]:
    if mode not in IDIOM_MODES:
        raise ValueError(f"idiom mode must be one of {IDIOM_MODES}")
    out = []
    for c in sorted(accepted, key=lambda c: c.start):
        span = text[c.start:c.end]
        rep = case_for_position(c.paraphrase, text, c.start) if mode == "paraphrase" else HINT_TEMPLATE.format(span=span, gloss=c.paraphrase)
        out.append(Rewrite("idiom", c.idiom_id, c.start, c.end, span, rep))
    return out


def apply_idioms(text: str, accepted: list[IdiomCandidate], mode: str) -> tuple[str, list[Rewrite]]:
    rw = idiom_rewrites(text, accepted, mode)
    return apply_rewrites(text, rw), rw
