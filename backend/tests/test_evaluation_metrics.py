"""Unit tests: BLEU / chrF++ / SPR / statistics against hand-computed values.
All ratings here are SYNTHETIC test fixtures, not human judgments."""
import pytest

from app.evaluation.overlap_metrics import corpus_score, paired_bootstrap, score_all
from app.evaluation.spr import delta_spr, harmful_intervention_rate, spr_by, spr_summary
from app.evaluation.statistics import bootstrap_ci_proportion, cohens_kappa, mcnemar_exact, paired_bootstrap_delta


def test_bleu_and_chrf_identical_is_100_and_signature_names_tokenizer():
    hyps = ["the cat sat on the mat", "a quick brown fox"]
    s = score_all(hyps, hyps, metrics=("bleu_13a", "chrfpp"))
    assert s["bleu_13a"]["score"] == 100.0 and s["chrfpp"]["score"] == 100.0
    assert "tok:13a" in s["bleu_13a"]["signature"]
    assert "nw:2" in s["chrfpp"]["signature"]  # chrF++ = word order 2


def test_bleu_disjoint_is_zero_and_length_mismatch_errors():
    assert corpus_score("bleu_13a", ["x y z w"], ["a b c d"])["score"] == 0.0
    with pytest.raises(ValueError):
        corpus_score("bleu_13a", ["a"], ["a", "b"])
    assert corpus_score("chrfpp", [], [])["score"] is None


def test_paired_bootstrap_detects_clear_difference():
    refs = [f"sentence number {i} is here" for i in range(30)]
    good = list(refs)
    bad = [f"completely different words {i}" for i in range(30)]
    r = paired_bootstrap("chrfpp", bad, good, refs, n_samples=200)
    assert r["delta"] > 50 and r["ci95"][0] > 0 and r["p_b_not_better"] == 0.0


def test_spr_strict_counts_only_preserved():
    s = spr_summary(["preserved", "preserved", "partial", "not_preserved"])
    assert s["spr"] == 50.0 and s["partial_rate"] == 25.0 and s["not_preserved_rate"] == 25.0
    assert s["spr_ci95"][0] <= 50.0 <= s["spr_ci95"][1]
    with pytest.raises(ValueError):
        spr_summary(["good"])
    assert spr_summary([])["spr"] is None


def test_overall_spr_is_pooled_not_averaged():
    items = [{"rating": "preserved", "cat": "idiom"}] * 70 + [{"rating": "not_preserved", "cat": "idiom"}] * 30 \
          + [{"rating": "preserved", "cat": "context"}] * 10 + [{"rating": "not_preserved", "cat": "context"}] * 40
    by = spr_by(items, "cat")
    assert by["idiom"]["spr"] == 70.0 and by["context"]["spr"] == 20.0
    overall = spr_summary([i["rating"] for i in items])
    assert overall["spr"] == pytest.approx(53.33, abs=0.01)  # 80/150, not (70+20)/2 = 45


def test_delta_spr_and_relative_change():
    base = ["preserved"] * 5 + ["not_preserved"] * 5
    var = ["preserved"] * 8 + ["not_preserved"] * 2
    d = delta_spr(base, var)
    assert d["spr_baseline"] == 50.0 and d["spr_variant"] == 80.0
    assert d["delta_pp"] == 30.0 and d["delta_relative_pct"] == 60.0
    assert d["mcnemar"]["n01_improved"] == 3 and d["mcnemar"]["n10_worsened"] == 0


def test_mcnemar_exact_hand_values():
    assert mcnemar_exact([0] * 5, [1] * 5)["p_value"] == pytest.approx(0.0625)
    assert mcnemar_exact([1, 0], [1, 0])["p_value"] == 1.0  # no discordant pairs
    r = mcnemar_exact([0, 0, 0, 1], [1, 1, 1, 0])  # n01=3, n10=1 -> p = 2*(1+4)/16 = 0.625
    assert r["p_value"] == pytest.approx(0.625)


def test_cohens_kappa_hand_value():
    k = cohens_kappa(["a", "a", "b", "b"], ["a", "b", "b", "b"])
    assert k["observed_agreement"] == 0.75 and k["expected_agreement"] == 0.5 and k["kappa"] == pytest.approx(0.5)
    assert cohens_kappa(["x", "y"], ["x", "y"])["kappa"] == 1.0


def test_bootstrap_helpers_are_seeded():
    s = [1, 0, 1, 1, 0, 1, 0, 1]
    assert bootstrap_ci_proportion(s) == bootstrap_ci_proportion(s)
    d = paired_bootstrap_delta([0] * 10, [1] * 10)
    assert d["delta"] == 1.0 and d["ci95"] == [1.0, 1.0]


def test_harmful_intervention_rate_uses_activations_as_denominator():
    pairs = [
        {"intervened": True, "baseline_rating": "preserved", "variant_rating": "partial"},       # harmful
        {"intervened": True, "baseline_rating": "not_preserved", "variant_rating": "preserved"},  # helpful
        {"intervened": True, "baseline_rating": "preserved", "variant_rating": "preserved"},
        {"intervened": True, "baseline_rating": "partial", "variant_rating": "partial"},
        {"intervened": False, "baseline_rating": "preserved", "variant_rating": "not_preserved"},  # not an activation
    ]
    h = harmful_intervention_rate(pairs)
    assert h["activations"] == 4 and h["harmful"] == 1 and h["harmful_intervention_rate"] == 25.0
    assert h["helpful_intervention_rate"] == 25.0
