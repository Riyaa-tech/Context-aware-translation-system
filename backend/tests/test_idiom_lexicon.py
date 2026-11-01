"""Unit tests: idiom lexicon schema and lookup (no model)."""
import copy

import pytest

from app.modules.idiom_lexicon import LexiconError, load_lexicon, load_lexicon_from_dict, poss_to_obj

META, ENTRIES = load_lexicon()


def test_lexicon_loads_with_required_languages():
    langs = {e.source_language for e in ENTRIES}
    assert {"eng_Latn", "hin_Deva", "spa_Latn"} <= langs
    assert len({e.idiom_id for e in ENTRIES}) == len(ENTRIES)


def test_all_entries_are_honestly_marked_draft():
    # Nothing has been human-reviewed yet; the lexicon must not claim otherwise.
    assert all(e.review_status == "draft" for e in ENTRIES)


def test_example_context_matches_own_entry():
    """Each entry's own example sentence must be found by at least one of its forms."""
    from app.modules.idiom_detector import IdiomDetector

    det = IdiomDetector()
    missing = [e.idiom_id for e in ENTRIES
               if e.idiom_id not in {c.idiom_id for c in det.detect(e.example_context, e.source_language)}]
    assert missing == []


def _raw():
    return {"entries": [{
        "idiom_id": "T_1", "expression": "x", "source_language": "eng_Latn", "intended_meaning": "m",
        "literal_meaning": "l", "example_context": "e", "provenance": "p", "confidence": 0.9,
        "review_status": "draft", "forms": [{"surface": "spill the beans", "paraphrase": "reveal the secret"}]}]}


def test_validation_rejects_missing_field():
    raw = _raw()
    del raw["entries"][0]["provenance"]
    with pytest.raises(LexiconError, match="missing"):
        load_lexicon_from_dict(raw)


def test_validation_rejects_bad_status_and_confidence():
    raw = _raw(); raw["entries"][0]["review_status"] = "approved"
    with pytest.raises(LexiconError):
        load_lexicon_from_dict(raw)
    raw = _raw(); raw["entries"][0]["confidence"] = 1.5
    with pytest.raises(LexiconError):
        load_lexicon_from_dict(raw)


def test_validation_rejects_duplicate_ids_and_unbound_slots():
    raw = _raw(); raw["entries"].append(copy.deepcopy(raw["entries"][0]))
    with pytest.raises(LexiconError, match="duplicate"):
        load_lexicon_from_dict(raw)
    raw = _raw(); raw["entries"][0]["forms"][0]["paraphrase"] = "tease {obj}"
    with pytest.raises(LexiconError, match="slot"):
        load_lexicon_from_dict(raw)


@pytest.mark.parametrize("poss,obj", [("my", "me"), ("your", "you"), ("her", "her"), ("John's", "John"), ("My", "Me")])
def test_poss_to_obj(poss, obj):
    assert poss_to_obj(poss) == obj
