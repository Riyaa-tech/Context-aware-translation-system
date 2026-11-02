"""Unit tests: NLLB language configuration (no model)."""
import pytest

from app.config.languages import DIRECTIONS, LANGUAGES, RETIRED_LANGUAGES, LanguageError, check_direction, normalize_code


def test_ten_directions_four_enabled():
    assert len(DIRECTIONS) == 10
    enabled = {d.key for d in DIRECTIONS if d.status == "enabled"}
    assert enabled == {
        "eng_Latn-hin_Deva", "hin_Deva-eng_Latn", "eng_Latn-deu_Latn", "deu_Latn-eng_Latn",
    }


def test_all_direction_codes_are_known_languages():
    for d in DIRECTIONS:
        assert d.source in LANGUAGES and d.target in LANGUAGES


@pytest.mark.parametrize("alias,code", [("en", "eng_Latn"), ("HI", "hin_Deva"), ("de", "deu_Latn"), ("DE", "deu_Latn"), ("deu_Latn", "deu_Latn")])
def test_normalize(alias, code):
    assert normalize_code(alias) == code


def test_unknown_code():
    with pytest.raises(LanguageError):
        normalize_code("klingon")


def test_same_language_rejected():
    with pytest.raises(LanguageError, match="different"):
        check_direction("eng_Latn", "eng_Latn")


def test_planned_direction_blocked_by_default():
    with pytest.raises(LanguageError, match="not yet tested"):
        check_direction("fra_Latn", "arb_Arab")
    assert check_direction("fra_Latn", "arb_Arab", allow_planned=True).status == "planned"


def test_unconfigured_direction():
    with pytest.raises(LanguageError, match="not part"):
        check_direction("swh_Latn", "zho_Hans", allow_planned=True)


# ---- German scope (2026-11-02): Spanish removed, German added ----
def test_german_directions_enabled_both_ways():
    assert check_direction("eng_Latn", "deu_Latn").status == "enabled"
    assert check_direction("deu_Latn", "eng_Latn").status == "enabled"
    assert LANGUAGES["deu_Latn"] == "German"


def test_hindi_german_directions_are_planned_not_enabled():
    for s, t in (("hin_Deva", "deu_Latn"), ("deu_Latn", "hin_Deva")):
        with pytest.raises(LanguageError, match="not yet tested"):
            check_direction(s, t)
        assert check_direction(s, t, allow_planned=True).status == "planned"


@pytest.mark.parametrize("code", ["es", "ES", "spa_Latn"])
def test_spanish_codes_rejected_with_explanation(code):
    with pytest.raises(LanguageError, match="Spanish was removed"):
        normalize_code(code)


def test_no_spanish_direction_remains():
    assert "spa_Latn" not in LANGUAGES and "spa_Latn" in RETIRED_LANGUAGES
    assert not [d for d in DIRECTIONS if "spa_Latn" in (d.source, d.target)]
