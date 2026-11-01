"""Unit tests: NLLB language configuration (no model)."""
import pytest

from app.config.languages import DIRECTIONS, LANGUAGES, LanguageError, check_direction, normalize_code


def test_ten_directions_four_enabled():
    assert len(DIRECTIONS) == 10
    enabled = {d.key for d in DIRECTIONS if d.status == "enabled"}
    assert enabled == {
        "eng_Latn-hin_Deva", "hin_Deva-eng_Latn", "eng_Latn-spa_Latn", "spa_Latn-eng_Latn",
    }


def test_all_direction_codes_are_known_languages():
    for d in DIRECTIONS:
        assert d.source in LANGUAGES and d.target in LANGUAGES


@pytest.mark.parametrize("alias,code", [("en", "eng_Latn"), ("HI", "hin_Deva"), ("spa_Latn", "spa_Latn")])
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
