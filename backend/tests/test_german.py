"""German scope (2026-11-02): German idiom matching, paraphrase/hint, controller behaviour, casing,
dataset validation, and Spanish rejection. No model (MOCKED engine where a pipeline is needed)."""
import json

import pytest

from app.controller.semantic_controller import ABSTAIN, INTERVENE, PASS_THROUGH, SemanticController
from app.experiments.datasets import load_challenge_files, validate_row
from app.experiments.runner import ROOT
from app.modules.idiom_detector import IdiomDetector
from app.modules.idiom_lexicon import LexiconError, load_lexicon, load_lexicon_from_dict
from app.modules.idiom_resolver import apply_idioms
from app.modules.text_utils import at_sentence_start, case_for_position
from app.pipeline import PipelineConfig, SemanticPipeline
from tests.conftest import FakeEngine

DET, CTRL = IdiomDetector(), SemanticController()
DE = "deu_Latn"


def decide(text):
    cands = DET.detect(text, DE)
    return cands, CTRL.decide(cands)


def para(text, mode="paraphrase"):
    _, out = decide(text)
    assert out.decision == INTERVENE, (text, out)
    return apply_idioms(text, out.accepted_idioms, mode)[0]


# ---------------- lexicon content ----------------
def test_german_entries_are_drafts_with_sources():
    de = [e for e in load_lexicon()[1] if e.source_language == DE]
    assert len(de) == 8
    for e in de:
        assert e.review_status == "draft"  # AI-generated; not human-reviewed yet
        assert e.extra["supported_directions"] == ["deu_Latn-eng_Latn"]
        assert e.extra["source_reference"]["url"].startswith("https://www.duden.de/")
        assert e.literal_meaning and e.intended_meaning and e.extra["english_equivalent"]


def test_spanish_entries_only_in_legacy_file():
    assert not [e for e in load_lexicon()[1] if e.source_language == "spa_Latn"]
    legacy = json.loads((ROOT / "backend/resources/idioms/legacy/lexicon_v0.1_spanish_entries.json").read_text(encoding="utf-8"))
    assert len(legacy["entries"]) == 6 and {e["source_language"] for e in legacy["entries"]} == {"spa_Latn"}


# ---------------- matching across German word orders ----------------
@pytest.mark.parametrize("text,expected", [
    ("Das glaube ich dir nicht, du nimmst mich auf den Arm!", "Das glaube ich dir nicht, du hältst mich zum Narren!"),   # main clause
    ("Willst du mich auf den Arm nehmen?", "Willst du mich zum Narren halten?"),                                         # infinitive
    ("Ich weiß, dass er mich ständig auf den Arm nimmt.", "Ich weiß, dass er mich ständig zum Narren hält."),            # subordinate + {gap}
    ("Sie hat ihren Kollegen gestern auf den Arm genommen.", "Sie hat ihren Kollegen gestern zum Narren gehalten."),     # perfect, NP object
    ("Hör auf, mich auf den Arm zu nehmen!", "Hör auf, mich zum Narren zu halten!"),                                     # zu-infinitive
    ("Nimmst du mich auf den Arm?", "Hältst du mich zum Narren?"),                                                       # verb-first + {gap2}
    ("Du hast wohl Tomaten auf den Augen!", "Du übersiehst wohl das Offensichtliche!"),
    ("Mit seiner Bemerkung ist er ins Fettnäpfchen getreten.", "Mit seiner Bemerkung hat er einen Fauxpas begangen."),   # sein -> haben
    ("Ich hoffe, dass ich nicht wieder ins Fettnäpfchen trete.", "Ich hoffe, dass ich nicht wieder einen Fauxpas begehe."),
    ("Meine Großmutter nimmt kein Blatt vor den Mund.", "Meine Großmutter redet ganz offen."),
    ("Die Prüfung war für ihn ein Kinderspiel.", "Die Prüfung war für ihn sehr einfach."),
    ("Ich drücke dir morgen die Daumen!", "Ich wünsche dir morgen viel Glück!"),                                         # {dat}{gap}
    ("Drückst du mir die Daumen?", "Wünschst du mir viel Glück?"),                                                       # {gap2}{dat}
    ("Wir drücken die Daumen.", "Wir wünschen viel Glück."),
    ("Da bist du auf dem Holzweg.", "Da bist du im Irrtum."),
    ("Ich verstehe nur Bahnhof.", "Ich verstehe überhaupt nichts."),
    ("Er erklärte es so, dass ich nur Bahnhof verstand.", "Er erklärte es so, dass ich überhaupt nichts verstand."),
])
def test_german_paraphrase_mode(text, expected):
    assert para(text) == expected


def test_german_hint_mode_keeps_idiom_and_adds_gloss():
    assert para("Ich verstehe nur Bahnhof.", "hint") == "Ich verstehe nur Bahnhof (verstehe überhaupt nichts)."
    assert para("Da bist du auf dem Holzweg.", "hint") == "Da bist du auf dem Holzweg (im Irrtum)."


def test_umlaut_and_case_insensitive_matching():
    assert DET.detect("ER IST INS FETTNÄPFCHEN GETRETEN.", DE)[0].idiom_id == "DE_003"
    assert DET.detect("Er   ist ins\nFettnäpfchen getreten.", DE)[0].idiom_id == "DE_003"


def test_no_partial_word_or_unlisted_variant_match():
    assert DET.detect("Sie nimmt nie ein Blatt vor den Mund.", DE) == []   # variant not covered (documented gap)
    assert DET.detect("Wir halten dir die Daumen.", DE) == []             # 'Daumen halten' not covered
    assert DET.detect("Ich habe Tomaten und Gurken gekauft.", DE) == []


def test_german_entries_only_for_german_source():
    assert DET.detect("Ich verstehe nur Bahnhof.", "eng_Latn") == []
    assert DET.detect("She spilled the beans.", DE) == []


# ---------------- literal vs figurative, controller decisions ----------------
@pytest.mark.parametrize("text,idiom", [
    ("Die Mutter nimmt das weinende Kind auf den Arm.", "DE_001"),      # cue captured by the {akk} slot
    ("Der Vater nimmt seinen kleinen Sohn auf den Arm.", "DE_001"),
    ("Fangen ist ein Kinderspiel, das schon im Kindergarten beliebt ist.", "DE_005"),
    ("Wir wanderten auf dem Holzweg durch den Wald.", "DE_007"),
])
def test_german_literal_controls_pass_through(text, idiom):
    cands, out = decide(text)
    assert cands[0].idiom_id == idiom and cands[0].usage == "literal"
    assert out.decision == PASS_THROUGH and out.span_decisions[0].action == "reject_literal"


def test_slot_words_count_as_evidence():
    c = DET.detect("Die Mutter nimmt das weinende Kind auf den Arm.", DE)[0]
    assert "kind" in c.literal_cues_found


def test_mixed_german_evidence_abstains():
    # prior 0.8 + figurative cue 'witz' (+0.1) - literal cue 'kind' (-0.4) = 0.5 -> uncertain
    cands, out = decide("Das war nur ein Witz, er nimmt das Kind auf den Arm.")
    assert cands[0].usage == "uncertain" and out.decision == ABSTAIN and "DE_001" in out.abstention_reason


def test_figurative_german_intervenes_with_reason():
    _, out = decide("Wenn du glaubst, dass ich es war, bist du auf dem Holzweg.")
    assert out.decision == INTERVENE and out.span_decisions[0].action == "accept"


def test_ordinary_german_sentence_passes_through():
    assert decide("Der Zug nach Berlin fährt um acht Uhr ab.")[1].decision == PASS_THROUGH


# ---------------- casing by sentence position ----------------
def test_case_for_position():
    t = "Man muss Tomaten auf den Augen haben."
    assert not at_sentence_start(t, t.index("Tomaten"))
    assert case_for_position("das Offensichtliche übersehen", t, t.index("Tomaten")) == "das Offensichtliche übersehen"
    assert case_for_position("das Offensichtliche übersehen", "Tomaten …", 0) == "Das Offensichtliche übersehen"
    q = "Er sagte: „Du nimmst mich auf den Arm.“"
    assert at_sentence_start(q, q.index("Du"))


def test_mid_sentence_german_noun_does_not_capitalise_paraphrase():
    assert para("Man muss Tomaten auf den Augen haben, um das nicht zu sehen.") == \
        "Man muss das Offensichtliche übersehen, um das nicht zu sehen."
    assert para("Tomaten auf den Augen haben ist keine Ausrede.") == "Das Offensichtliche übersehen ist keine Ausrede."


# ---------------- slot validation ----------------
def _doc(surface, paraphrase):
    return {"entries": [{"idiom_id": "T", "expression": "x", "source_language": DE, "intended_meaning": "m",
                         "literal_meaning": "l", "example_context": "e", "provenance": "p", "confidence": 0.9,
                         "review_status": "draft", "forms": [{"surface": surface, "paraphrase": paraphrase}]}]}


def test_slot_validation():
    load_lexicon_from_dict(_doc("nimmt {akk}{gap} auf den Arm", "hält {akk}{gap} zum Narren"))
    with pytest.raises(LexiconError, match="slot"):
        load_lexicon_from_dict(_doc("nimmt {akk} auf den Arm", "hält {akk}{gap} zum Narren"))
    with pytest.raises(LexiconError, match="slot"):
        load_lexicon_from_dict(_doc("drückt die Daumen", "wünscht {dat} viel Glück"))
    with pytest.raises(LexiconError, match="mix"):
        load_lexicon_from_dict(_doc("pull {poss} leg {akk}", "tease {obj}"))


# ---------------- pipeline (MOCKED engine) ----------------
def test_pipeline_german_to_english_sends_paraphrase():
    eng = FakeEngine()
    pr = SemanticPipeline(eng, PipelineConfig(idiom_mode="paraphrase")).run("Ich verstehe nur Bahnhof.", DE, "eng_Latn")
    assert eng.calls[0] == (["Ich verstehe überhaupt nichts."], DE, "eng_Latn")
    assert pr.record["module_predictions"]["idiom"][0]["review_status"] == "draft"


def test_pipeline_english_to_german_uses_english_lexicon():
    eng = FakeEngine()
    SemanticPipeline(eng, PipelineConfig(idiom_mode="paraphrase")).run("She finally spilled the beans.", "eng_Latn", DE)
    assert eng.calls[0] == (["She finally revealed the secret."], "eng_Latn", DE)


# ---------------- dataset validation ----------------
def _row(**kw):
    r = {"example_id": "X1", "source_language": DE, "target_language": "eng_Latn", "category": "idiom",
         "source_text": "Ich verstehe nur Bahnhof.", "context": [], "intended_meaning": "I understand nothing.",
         "reference_translation": None, "provenance": "manually authored by tester", "split": "dev"}
    r.update(kw)
    return r


def test_german_rows_validate():
    assert validate_row(_row(), 1, "t") == []
    assert validate_row(_row(source_language="eng_Latn", target_language=DE), 1, "t") == []


@pytest.mark.parametrize("side", ["source_language", "target_language"])
def test_spanish_rows_rejected(side):
    errs = validate_row(_row(**{side: "spa_Latn"}), 1, "t")
    assert errs and "no longer supported" in errs[0] and side in errs[0]


def test_v2_dev_files_are_valid_and_spanish_free():
    files = [ROOT / f"experiments/datasets/challenge_set/{n}_dev_v2.jsonl" for n in ("idiom", "context", "sarcasm")]
    ds = load_challenge_files(files)
    assert ds.errors == []
    dirs = {(r["source_language"], r["target_language"]) for r in ds.rows}
    assert dirs == {("eng_Latn", "hin_Deva"), ("hin_Deva", "eng_Latn"), ("eng_Latn", DE), (DE, "eng_Latn")}


def test_legacy_spanish_dev_files_are_rejected_but_kept():
    legacy = ROOT / "experiments/datasets/challenge_set/legacy_v1_spanish/idiom_dev.jsonl"
    assert legacy.exists()
    assert any("no longer supported" in e for e in load_challenge_files([legacy]).errors)
