"""M1 step 3: build the modified NLLB input from accepted idiom candidates.

Modes (compared in the experiment, paper Section IV-E):
  hint        -> keep the idiom and add its meaning in brackets: "spilled the beans (revealed the secret)"
  paraphrase  -> replace the idiom with its controlled paraphrase: "revealed the secret"
"""
from __future__ import annotations

from dataclasses import dataclass

from app.modules.idiom_detector import IdiomCandidate
from app.modules.text_utils import match_case

IDIOM_MODES = ("hint", "paraphrase")
HINT_TEMPLATE = "{span} ({gloss})"


@dataclass
class Rewrite:
    idiom_id: str
    start: int
    end: int
    original_span: str
    replacement: str


def apply_idioms(text: str, accepted: list[IdiomCandidate], mode: str) -> tuple[str, list[Rewrite]]:
    if mode not in IDIOM_MODES:
        raise ValueError(f"idiom mode must be one of {IDIOM_MODES}")
    rewrites: list[Rewrite] = []
    out = text
    # Apply right-to-left so earlier offsets stay valid.
    for c in sorted(accepted, key=lambda c: c.start, reverse=True):
        span = text[c.start:c.end]
        if mode == "paraphrase":
            rep = match_case(c.paraphrase, span)
        else:
            rep = HINT_TEMPLATE.format(span=span, gloss=c.paraphrase)
        out = out[: c.start] + rep + out[c.end:]
        rewrites.append(Rewrite(c.idiom_id, c.start, c.end, span, rep))
    rewrites.reverse()
    return out, rewrites
