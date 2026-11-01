"""Reference-based overlap metrics via SacreBLEU (paper Section III-B).

Score names always carry the tokenizer so that 13a BLEU is never reported as FLORES spBLEU:
  bleu_13a          SacreBLEU BLEU, tokenizer 13a
  spbleu_flores200  SacreBLEU BLEU, tokenizer flores200 (SentencePiece, as used for FLORES-200)
  chrfpp            chrF++ (char order 6, word order 2, beta 2)
Every result includes the SacreBLEU signature string for reproducibility.
"""
from __future__ import annotations

import random
from functools import lru_cache

from sacrebleu.metrics import BLEU, CHRF

METRICS = ("bleu_13a", "spbleu_flores200", "chrfpp")


@lru_cache(maxsize=None)
def _metric(name: str, target_lang: str | None = None):
    if name == "bleu_13a":
        # 13a is designed for whitespace-separated languages; flag it for Chinese.
        return BLEU(tokenize="13a")
    if name == "spbleu_flores200":
        return BLEU(tokenize="flores200")
    if name == "chrfpp":
        return CHRF(word_order=2)
    raise ValueError(f"unknown metric {name}")


def corpus_score(name: str, hyps: list[str], refs: list[str]) -> dict:
    if len(hyps) != len(refs):
        raise ValueError("hypotheses and references differ in length")
    if not hyps:
        return {"metric": name, "score": None, "n": 0, "signature": None}
    m = _metric(name)
    s = m.corpus_score(hyps, [refs])
    return {"metric": name, "score": round(s.score, 2), "n": len(hyps), "signature": str(m.get_signature())}


def score_all(hyps: list[str], refs: list[str], metrics=METRICS) -> dict:
    return {name: corpus_score(name, hyps, refs) for name in metrics}


def paired_bootstrap(name: str, hyps_a: list[str], hyps_b: list[str], refs: list[str],
                     n_samples: int = 1000, seed: int = 12345) -> dict:
    """Paired bootstrap resampling (Koehn 2004): resample sentence indices with replacement,
    compute corpus scores for A and B on the same sample. Returns the 95% CI of (B - A) and the
    share of samples where B does not beat A (one-sided p-value estimate)."""
    n = len(refs)
    if not (len(hyps_a) == len(hyps_b) == n) or n == 0:
        raise ValueError("paired bootstrap needs equal, non-empty lists")
    m = _metric(name)
    rng = random.Random(seed)
    base_a = m.corpus_score(hyps_a, [refs]).score
    base_b = m.corpus_score(hyps_b, [refs]).score
    deltas = []
    for _ in range(n_samples):
        idx = [rng.randrange(n) for _ in range(n)]
        r = [refs[i] for i in idx]
        deltas.append(m.corpus_score([hyps_b[i] for i in idx], [r]).score - m.corpus_score([hyps_a[i] for i in idx], [r]).score)
    deltas.sort()
    lo, hi = deltas[int(0.025 * n_samples)], deltas[int(0.975 * n_samples) - 1]
    return {"metric": name, "a": round(base_a, 2), "b": round(base_b, 2), "delta": round(base_b - base_a, 2),
            "ci95": [round(lo, 2), round(hi, 2)], "p_b_not_better": round(sum(d <= 0 for d in deltas) / n_samples, 4),
            "n_samples": n_samples, "seed": seed, "n_sentences": n}
