"""Unit tests: context relevance, selection and sense resolution (no model)."""
import pytest

from app.modules.context_selector import (
    CONTEXT_AMBIGUOUS, CONTEXT_INSUFFICIENT, CONTEXT_IRRELEVANT, NO_CONTEXT_REQUIRED,
    RELEVANT_CONTEXT_SELECTED, ContextConfig, ContextSelector, context_rewrites,
)
from app.modules.sense_inventory import InventoryError, load_inventory, load_inventory_from_dict

SEL = ContextSelector()
BANK = "He went to the bank."


def analyze(text, ctx=None, sel=SEL):
    return SEL.analyze(text, "eng_Latn", ctx) if sel is SEL else sel.analyze(text, "eng_Latn", ctx)


def test_paper_example_riverbank():
    a = analyze(BANK, ["The fisherman sat beside the river."])
    w = a.words[0]
    assert a.state == RELEVANT_CONTEXT_SELECTED and w.resolved_sense == "bank.river" and w.replacement == "riverbank"
    assert a.selected_context == ["The fisherman sat beside the river."]
    assert context_rewrites(BANK, a.words)[0].replacement == "riverbank"


def test_dominant_sense_resolved_without_rewrite():
    a = analyze(BANK, ["He needed to deposit his salary."])
    assert a.state == RELEVANT_CONTEXT_SELECTED and a.words[0].replacement is None
    assert context_rewrites(BANK, a.words) == []


def test_four_states():
    assert analyze("The weather is nice today.").state == NO_CONTEXT_REQUIRED          # no ambiguous word
    assert analyze("He went to the bank to withdraw cash.", ["The river was calm."]).state == NO_CONTEXT_REQUIRED
    assert analyze(BANK).state == CONTEXT_INSUFFICIENT
    assert analyze(BANK, ["The weather was lovely that morning."]).state == CONTEXT_IRRELEVANT
    a = analyze(BANK, ["He needed money.", "The river looked calm."])  # equal support, both distance-weighted
    assert a.state in (CONTEXT_AMBIGUOUS, RELEVANT_CONTEXT_SELECTED)


def test_ambiguous_when_both_senses_supported_equally():
    a = analyze(BANK, ["He had money and he saw the river."])  # one cue per sense
    assert a.state == CONTEXT_AMBIGUOUS and a.words[0].replacement is None


def test_irrelevant_sentences_not_selected():
    a = analyze(BANK, ["It was a sunny morning.", "The fisherman sat beside the river.", "He smiled."])
    assert a.state == RELEVANT_CONTEXT_SELECTED
    assert a.selected_context == ["The fisherman sat beside the river."]
    assert [s.selected for s in a.words[0].sentence_scores] == [False, True, False]


def test_sliding_window_drops_old_sentences():
    ctx = ["The fisherman sat beside the river.", "A.", "B.", "C."]
    assert analyze(BANK, ctx).state == CONTEXT_IRRELEVANT  # river sentence is outside window of 3
    wide = ContextSelector(config=ContextConfig(window_size=4))
    assert wide.analyze(BANK, "eng_Latn", ctx).state == RELEVANT_CONTEXT_SELECTED


def test_recency_weighting_prefers_nearer_sentence():
    a = analyze(BANK, ["She needed money for rent.", "The fisherman sat beside the river."])
    assert a.words[0].resolved_sense == "bank.river"
    s = a.words[0].sentence_scores
    assert s[0].weight == pytest.approx(0.8) and s[1].weight == 1.0


def test_other_words_and_plural_forms():
    a = analyze("Bats came out at dusk.", ["We explored the cave at night."])
    assert a.words[0].replacement == "Bat animals"
    a = analyze("I can't find my glasses.", ["I wanted to read the newspaper."])
    assert a.words[0].replacement == "eyeglasses"


def test_inventory_loads_and_validates():
    meta, words = load_inventory()
    assert len(words) == 10 and meta["review_status"] == "draft"
    bad = {"words": [{"word_id": "X", "lemma": "x", "source_language": "eng_Latn", "forms": ["x"],
                      "senses": [{"sense_id": "x.1", "gloss": "g", "cues": [], "replacements": {"x": "y"}}]}]}
    with pytest.raises(InventoryError, match="two senses"):
        load_inventory_from_dict(bad)


def test_only_source_language_words():
    assert analyze_lang("Fue al banco.", "spa_Latn").words == []


def analyze_lang(text, lang):
    return SEL.analyze(text, lang, ["El pescador estaba junto al río."])
