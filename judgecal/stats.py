"""Agreement statistics used by every table in the report.

Thin wrappers over established libraries so that each number in the report comes from one place:
  - Wilson score interval ........ statsmodels.stats.proportion.proportion_confint
  - Cohen's kappa (plain, weighted) sklearn.metrics.cohen_kappa_score
  - Fleiss' kappa ................ statsmodels.stats.inter_rater.fleiss_kappa
  - Krippendorff's alpha ......... krippendorff.alpha
  - Spearman / Kendall ........... scipy.stats
  - exact McNemar test ........... scipy.stats.binomtest on the discordant pairs
Gwet's AC1 and the percentile bootstrap are a few lines each and are written here; the tests check
AC1 against a published worked example and the bootstrap against a closed-form case.

All intervals are 95%. The bootstrap resamples ITEMS (not single judgments), so repeated judgments of the
same item stay together, and uses a fixed seed so a re-run prints the same interval.
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

SEED = 20261118
N_BOOT = 2000


def wilson(k: int, n: int) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (float("nan"), float("nan"))
    from statsmodels.stats.proportion import proportion_confint

    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson")
    return (max(0.0, float(lo)), min(1.0, float(hi)))


def rate(k: int, n: int) -> dict:
    """A proportion with its Wilson interval, in the shape the report tables use."""
    lo, hi = wilson(k, n)
    return {"k": int(k), "n": int(n), "rate": (k / n if n else float("nan")), "lo": lo, "hi": hi}


def cohen_kappa(a: Sequence, b: Sequence, weights: str | None = None, labels: Sequence | None = None) -> float:
    """Cohen's kappa between two raters. weights='quadratic' for ordinal scales.

    Returns nan when both raters used one and the same single label (kappa is undefined there).
    """
    from sklearn.metrics import cohen_kappa_score

    if len(a) == 0:
        return float("nan")
    if len(set(a) | set(b)) < 2:
        return float("nan")
    return float(cohen_kappa_score(list(a), list(b), weights=weights, labels=list(labels) if labels else None))


def gwet_ac1(a: Sequence, b: Sequence) -> float:
    """Gwet's AC1 for two raters and nominal labels.

    AC1 = (pa - pe) / (1 - pe), with pe = 1/(q-1) * sum_k pi_k (1 - pi_k), pi_k the mean share of label k
    over both raters. Unlike kappa it stays informative when one label dominates (the 'kappa paradox').
    """
    n = len(a)
    if n == 0:
        return float("nan")
    cats = sorted(set(a) | set(b), key=str)
    q = len(cats)
    if q < 2:
        return float("nan")
    pa = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = 0.0
    for c in cats:
        pi = (sum(1 for x in a if x == c) + sum(1 for y in b if y == c)) / (2 * n)
        pe += pi * (1 - pi)
    pe /= (q - 1)
    return (pa - pe) / (1 - pe) if pe < 1 else float("nan")


def fleiss(table: Sequence[Sequence]) -> float:
    """Fleiss' kappa. table[i] is the list of labels the same item got from its repeated judgments."""
    from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

    arr = np.array([[str(x) for x in row] for row in table])
    if arr.size == 0 or len(set(arr.ravel())) < 2:
        return float("nan")
    counts, _ = aggregate_raters(arr)
    return float(fleiss_kappa(counts, method="fleiss"))


def kripp_alpha(rows: Sequence[Sequence], level: str = "ordinal") -> float:
    """Krippendorff's alpha. rows[r][i] is rater r's value for item i (None for missing)."""
    import krippendorff

    data = [[np.nan if v is None else float(v) for v in row] for row in rows]
    flat = [v for row in data for v in row if not (isinstance(v, float) and math.isnan(v))]
    if len(set(flat)) < 2:
        return float("nan")
    return float(krippendorff.alpha(reliability_data=data, level_of_measurement=level))


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    from scipy.stats import spearmanr

    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def kendall(a: Sequence[float], b: Sequence[float]) -> float:
    from scipy.stats import kendalltau

    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return float("nan")
    return float(kendalltau(a, b).statistic)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the two discordant counts."""
    from scipy.stats import binomtest

    if b + c == 0:
        return 1.0
    return float(binomtest(b, b + c, 0.5).pvalue)


def bootstrap(stat: Callable[[np.ndarray], float], n_items: int, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """95% percentile bootstrap interval. stat takes an array of item indices (with repeats) and returns a number."""
    if n_items == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        v = stat(rng.integers(0, n_items, n_items))
        if v is not None and not math.isnan(v):
            vals.append(v)
    if len(vals) < n_boot * 0.5:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (float(lo), float(hi))


def cluster_bootstrap(stat: Callable[[np.ndarray], float], clusters: Sequence, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """Percentile bootstrap that resamples whole clusters (all items about the same ad, resume or article
    stay together), because items of one cluster are not independent."""
    clusters = list(clusters)
    groups: dict = {}
    for i, c in enumerate(clusters):
        groups.setdefault(c, []).append(i)
    members = list(groups.values())
    if not members:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(members), len(members))
        idx = np.fromiter((i for g in pick for i in members[g]), dtype=int)
        v = stat(idx)
        if v is not None and not math.isnan(v):
            vals.append(v)
    if len(vals) < n_boot * 0.5:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (float(lo), float(hi))


def kappa_ci(a: Sequence, b: Sequence, weights: str | None = None, clusters: Sequence | None = None) -> dict:
    """Cohen's kappa with a bootstrap interval (over clusters when given, else over items)."""
    a, b = list(a), list(b)
    aa, bb = np.array([str(x) for x in a]), np.array([str(x) for x in b])
    if weights:
        aa, bb = np.array(a, dtype=float), np.array(b, dtype=float)
    k = cohen_kappa(list(aa), list(bb), weights)
    f = lambda idx: cohen_kappa(list(aa[idx]), list(bb[idx]), weights)  # noqa: E731
    lo, hi = cluster_bootstrap(f, clusters) if clusters is not None else bootstrap(f, len(a))
    return {"kappa": k, "lo": lo, "hi": hi, "n": len(a)}


def agreement_block(truth: Sequence, judged: Sequence, positive=None, clusters: Sequence | None = None) -> dict:
    """Everything one row of an agreement table needs: agreement rate, kappa, AC1 and, for a binary
    task with a named positive label, the two error rates (missed positives, false positives)."""
    truth, judged = list(truth), list(judged)
    n = len(truth)
    agree = sum(1 for t, j in zip(truth, judged) if t == j)
    out = {"n": n, "agreement": rate(agree, n), "kappa": kappa_ci(truth, judged, clusters=clusters), "ac1": gwet_ac1(truth, judged)}
    if positive is not None:
        pos = [j for t, j in zip(truth, judged) if t == positive]
        neg = [j for t, j in zip(truth, judged) if t != positive]
        out["recall"] = rate(sum(1 for j in pos if j == positive), len(pos))
        out["false_positive"] = rate(sum(1 for j in neg if j == positive), len(neg))
    return out
