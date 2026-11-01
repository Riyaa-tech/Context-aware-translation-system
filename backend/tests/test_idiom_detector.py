"""Unit tests: idiom detection and literal-vs-figurative assessment (no model)."""
import pytest

from app.modules.idiom_detector import IdiomConfig, IdiomDetector

DET = IdiomDetector()


def one(text, lang="eng_Latn", context=None):
    cs = DET.detect(text, lang, context)
    assert len(cs) == 1, cs
    return cs[0]


@pytest.mark.parametrize("text,idiom", [
    ("She finally spilled the beans about the party.", "EN_001"),
    ("SHE SPILLED THE BEANS.", "EN_001"),
    ("She   spilled  the\nbeans.", "EN_001"),            # whitespace normalization
    ("Stop beating about the bush.", "EN_011"),
    ("I’m feeling under the weather.", "EN_004"),     # curly apostrophe elsewhere
])
def test_exact_and_normalized_matching(text, idiom):
    assert one(text).idiom_id == idiom


def test_no_partial_word_matches():
    assert DET.detect("He respilled the beansprouts.", "eng_Latn") == []


def test_only_entries_for_source_language():
    assert DET.detect("She spilled the beans.", "spa_Latn") == []


@pytest.mark.parametrize("text", [
    "He spilled the beans all over the kitchen floor.",
    "She ate a piece of cake at the birthday party.",
    "Soak the beans in hot water overnight.",
    "The dog was barking up the wrong tree at a squirrel.",
    "Be careful on the ice or you'll break a leg.",
])
def test_literal_controls(text):
    assert one(text).usage == "literal"


@pytest.mark.parametrize("text", [
    "The exam was a piece of cake.",
    "He's in hot water with his boss.",
    "Break a leg at your audition tonight!",
    "If you think I took it, you're barking up the wrong tree.",
])
def test_figurative_uses(text):
    assert one(text).usage == "figurative"


def test_literal_follower_rule():
    c = one("He kicked the bucket of paint.")
    assert c.literal_follower_found == "of" and c.usage == "literal"


def test_context_sentences_provide_evidence():
    no_ctx = one("He broke the ice.")
    with_ctx = one("He broke the ice.", context=["We went skating on the frozen lake."])
    assert no_ctx.usage == "figurative"
    assert with_ctx.usage == "literal" and "lake" in with_ctx.literal_cues_found


def test_mixed_evidence_is_uncertain():
    # one figurative cue (+0.1) and one literal cue (-0.4) from prior 0.75 -> 0.45
    c = one("She told me she spilled the beans on the floor.")
    assert c.usage == "uncertain" and 0.4 < c.usage_score < 0.6


def test_possessive_slot_filled():
    c = one("Relax, I'm just pulling your leg.")
    assert c.paraphrase == "teasing you"
    assert one("They were pulling John's leg.").paraphrase == "teasing John"


def test_hindi_detection_with_danda():
    c = one("पुलिस को देखते ही चोर नौ दो ग्यारह हो गया।", "hin_Deva")
    assert c.idiom_id == "HI_002" and c.usage == "figurative" and c.paraphrase == "भाग गया"


def test_hindi_literal_control():
    assert one("माँ ने कहा कि दाल में कुछ काला है, शायद मसाला जल गया।", "hin_Deva").usage == "literal"


def test_spanish_detection_and_literal_control():
    assert one("Metí la pata cuando le pregunté por su ex.", "spa_Latn").usage == "figurative"
    assert one("El perro metió la pata en el agua.", "spa_Latn").usage == "literal"


def test_thresholds_are_configurable():
    strict = IdiomDetector(config=IdiomConfig(figurative_threshold=0.99))
    c = strict.detect("Break a leg!", "eng_Latn")[0]
    assert c.usage == "uncertain"
