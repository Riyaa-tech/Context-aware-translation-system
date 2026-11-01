"""Statistical tests for paired comparisons (paper Section IV-J).

- bootstrap_ci_proportion: percentile bootstrap CI for a rate (e.g. SPR)
- paired_bootstrap_delta: CI for the difference of two paired rates (e.g. ΔSPR)
- mcnemar_exact: exact two-sided McNemar test on paired binary outcomes
- cohens_kappa: agreement between two raters on categorical labels
No result is called "significant" unless the test was run; callers report p-values and CIs.
"""
from __future__ import annotations

import math
import random


def bootstrap_ci_proportion(successes: list[int], n_samples: int = 2000, seed: int = 12345) -> dict:
    n = len(successes)
    if n == 0:
        return {"rate": None, "ci95": None, "n": 0}
    rng = random.Random(seed)
    stats = sorted(sum(successes[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_samples))
    return {"rate": sum(successes) / n, "ci95": [stats[int(0.025 * n_samples)], stats[int(0.975 * n_samples) - 1]],
            "n": n, "n_samples": n_samples, "seed": seed}


def paired_bootstrap_delta(a: list[int], b: list[int], n_samples: int = 2000, seed: int = 12345) -> dict:
    """a, b: paired 0/1 outcomes for the same items (baseline, variant). Returns CI of mean(b) - mean(a)."""
    if len(a) != len(b):
        raise ValueError("paired lists must have the same length")
    n = len(a)
    if n == 0:
        return {"delta": None, "ci95": None, "n": 0}
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_samples):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append((sum(b[i] for i in idx) - sum(a[i] for i in idx)) / n)
    deltas.sort()
    return {"delta": (sum(b) - sum(a)) / n, "ci95": [deltas[int(0.025 * n_samples)], deltas[int(0.975 * n_samples) - 1]],
            "n": n, "n_samples": n_samples, "seed": seed}


def mcnemar_exact(a: list[int], b: list[int]) -> dict:
    """Exact (binomial) two-sided McNemar test.
    n01 = items where a=0 and b=1 (variant fixed it); n10 = a=1, b=0 (variant broke it)."""
    if len(a) != len(b):
        raise ValueError("paired lists must have the same length")
    n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
    n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
    m = n01 + n10
    if m == 0:
        p = 1.0
    else:
        k = min(n01, n10)
        p = min(1.0, 2 * sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m)
    return {"n01_improved": n01, "n10_worsened": n10, "discordant": m, "p_value": p, "test": "McNemar exact (binomial), two-sided",
            "n": len(a)}


def cohens_kappa(r1: list, r2: list) -> dict:
    if len(r1) != len(r2):
        raise ValueError("rater lists must have the same length")
    n = len(r1)
    if n == 0:
        return {"kappa": None, "n": 0}
    labels = sorted(set(r1) | set(r2), key=str)
    po = sum(x == y for x, y in zip(r1, r2)) / n
    pe = sum((r1.count(l) / n) * (r2.count(l) / n) for l in labels)
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    return {"kappa": kappa, "observed_agreement": po, "expected_agreement": pe, "n": n, "labels": labels}
