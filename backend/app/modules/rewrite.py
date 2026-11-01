"""Apply span replacements from any module to the original sentence."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rewrite:
    module: str  # idiom | context
    item_id: str  # idiom_id or word_id
    start: int
    end: int
    original_span: str
    replacement: str


def apply_rewrites(text: str, rewrites: list[Rewrite]) -> str:
    """Apply non-overlapping rewrites right-to-left so earlier offsets stay valid."""
    ordered = sorted(rewrites, key=lambda r: r.start)
    for a, b in zip(ordered, ordered[1:]):
        if a.end > b.start:
            raise ValueError(f"overlapping rewrites {a.item_id} / {b.item_id}")
    out = text
    for r in reversed(ordered):
        out = out[: r.start] + r.replacement + out[r.end:]
    return out
