"""Unit tests: hint and controlled-paraphrase rewriting (no model)."""
import pytest

from app.modules.idiom_detector import IdiomDetector
from app.modules.idiom_resolver import apply_idioms

DET = IdiomDetector()


def rewrite(text, mode, lang="eng_Latn"):
    cands = [c for c in DET.detect(text, lang) if c.usage == "figurative"]
    return apply_idioms(text, cands, mode)


def test_paraphrase_keeps_tense():
    assert rewrite("She finally spilled the beans.", "paraphrase")[0] == "She finally revealed the secret."
    assert rewrite("He is spilling the beans.", "paraphrase")[0] == "He is revealing the secret."


def test_hint_keeps_original_and_adds_gloss():
    out, rw = rewrite("She finally spilled the beans.", "hint")
    assert out == "She finally spilled the beans (revealed the secret)."
    assert rw[0].original_span == "spilled the beans"


def test_sentence_initial_capitalization():
    assert rewrite("Break a leg!", "paraphrase")[0] == "Good luck!"


def test_two_idioms_in_one_sentence():
    out, rw = rewrite("The exam was a piece of cake, so I was on cloud nine.", "paraphrase")
    assert out == "The exam was very easy, so I was extremely happy."
    assert [r.idiom_id for r in rw] == ["EN_005", "EN_012"]


def test_original_text_is_not_mutated():
    text = "She spilled the beans."
    rewrite(text, "paraphrase")
    assert text == "She spilled the beans."


def test_unknown_mode():
    with pytest.raises(ValueError):
        apply_idioms("x", [], "magic")
