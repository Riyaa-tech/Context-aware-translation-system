"""Language and direction registry.

Only directions whose status is "enabled" are accepted by the API by default.
"planned" directions are listed in the paper (Section III-A) but have not yet been
tested in this project, so they must not be presented as supported.
"""
from __future__ import annotations

from dataclasses import dataclass

# NLLB-200 / FLORES-200 language codes for the seven languages in the paper.
LANGUAGES: dict[str, str] = {
    "eng_Latn": "English",
    "hin_Deva": "Hindi",
    "spa_Latn": "Spanish",
    "fra_Latn": "French",
    "arb_Arab": "Arabic (Modern Standard)",
    "zho_Hans": "Chinese (Simplified)",
    "swh_Latn": "Swahili",
}

# Short aliases accepted by the API for convenience.
ALIASES: dict[str, str] = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "ar": "arb_Arab",
    "zh": "zho_Hans",
    "sw": "swh_Latn",
}


@dataclass(frozen=True)
class Direction:
    source: str
    target: str
    status: str  # "enabled" | "planned"

    @property
    def key(self) -> str:
        return f"{self.source}-{self.target}"


# The ten directions from the paper. The first four form the initial MVP set.
DIRECTIONS: list[Direction] = [
    Direction("eng_Latn", "hin_Deva", "enabled"),
    Direction("hin_Deva", "eng_Latn", "enabled"),
    Direction("eng_Latn", "spa_Latn", "enabled"),
    Direction("spa_Latn", "eng_Latn", "enabled"),
    Direction("hin_Deva", "spa_Latn", "planned"),
    Direction("spa_Latn", "hin_Deva", "planned"),
    Direction("fra_Latn", "arb_Arab", "planned"),
    Direction("arb_Arab", "hin_Deva", "planned"),
    Direction("zho_Hans", "fra_Latn", "planned"),
    Direction("swh_Latn", "hin_Deva", "planned"),
]


class LanguageError(ValueError):
    """Raised for unknown codes or directions that are not enabled."""


def normalize_code(code: str) -> str:
    """Map an alias or NLLB code to a canonical NLLB code, or raise LanguageError."""
    c = code.strip()
    if c in LANGUAGES:
        return c
    if c.lower() in ALIASES:
        return ALIASES[c.lower()]
    raise LanguageError(
        f"Unknown language code '{code}'. Use one of: {', '.join(LANGUAGES)} "
        f"(or aliases {', '.join(ALIASES)})."
    )


def get_direction(source: str, target: str) -> Direction | None:
    for d in DIRECTIONS:
        if d.source == source and d.target == target:
            return d
    return None


def check_direction(source: str, target: str, allow_planned: bool = False) -> Direction:
    """Validate a direction. Returns the Direction or raises LanguageError."""
    if source == target:
        raise LanguageError("Source and target language must be different.")
    d = get_direction(source, target)
    if d is None:
        raise LanguageError(
            f"Direction {source} -> {target} is not part of this study's configured directions."
        )
    if d.status != "enabled" and not allow_planned:
        raise LanguageError(
            f"Direction {source} -> {target} is planned but not yet tested in this project. "
            "Set ALLOW_PLANNED_DIRECTIONS=1 to try it anyway (results are unvalidated)."
        )
    return d
