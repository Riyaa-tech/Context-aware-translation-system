from fastapi import APIRouter, Query

from app.modules.idiom_lexicon import load_lexicon

router = APIRouter(prefix="/api", tags=["resources"])


@router.get("/idioms")
def list_idioms(source_language: str | None = Query(None)):
    meta, entries = load_lexicon()
    items = [e.public_dict() for e in entries if source_language in (None, e.source_language)]
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.source_language] = counts.get(e.source_language, 0) + 1
    return {"meta": meta, "counts_by_language": counts, "entries": items}
