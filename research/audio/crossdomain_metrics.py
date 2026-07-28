"""Cross-domain / cross-site evaluation metrics (numpy only, no torch).

Kept torch-free so it is unit-tested in CI without the audio stack, matching
``anomaly.py`` / ``eval_anomaly.py``. The torch inference driver lives in
``eval_crossdomain.py``.

The unit of evaluation is a matrix of softmax probabilities ``probs`` of shape
``(n_clips, n_labels)`` plus integer ``targets``. We report three views a
reviewer needs to separate:

- **raw argmax** — what the model predicts with no threshold;
- **deployment-calibrated** — apply per-class thresholds fitted on the model's
  own validation split (a clip is the highest-scoring class clearing its
  threshold, else background), i.e. the honest deploy-what-you-calibrated view;
- **threshold-free ranking** — ROC-AUC of each threat class's score vs
  background, which measures separability independent of any operating point
  (H4/H5: is the problem calibration, or overlapping distributions?).

Every scalar can be wrapped in a clip-level bootstrap CI via ``bootstrap_ci``.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

LABELS = ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]
BACKGROUND_LABEL = "background_unknown"
BACKGROUND_INDEX = LABELS.index(BACKGROUND_LABEL)
THREAT_INDICES = [i for i, l in enumerate(LABELS) if l != BACKGROUND_LABEL]


# ---------------------------------------------------------------------------
# Prediction rules
# ---------------------------------------------------------------------------

def argmax_predictions(probs: np.ndarray) -> np.ndarray:
    return np.asarray(probs, dtype=np.float64).argmax(axis=1)


def thresholded_predictions(probs: np.ndarray, thresholds: dict[str, float]) -> np.ndarray:
    """Highest-scoring class clearing its per-class threshold, else background.

    Mirrors ``research.audio.evaluate._thresholded_predictions`` exactly so the
    cross-domain numbers are comparable to the stored in-domain metrics.
    """
    probs = np.asarray(probs, dtype=np.float64)
    thr = np.array([float(thresholds.get(label, 0.5)) for label in LABELS])
    preds = np.full(probs.shape[0], BACKGROUND_INDEX, dtype=int)
    for i, row in enumerate(probs):
        passing = np.flatnonzero(row >= thr)
        if passing.size:
            preds[i] = passing[np.argmax(row[passing])]
    return preds


# ---------------------------------------------------------------------------
# Metrics over a fixed prediction vector
# ---------------------------------------------------------------------------

def per_class_recall(targets: np.ndarray, preds: np.ndarray) -> dict[str, float | None]:
    targets = np.asarray(targets)
    preds = np.asarray(preds)
    out: dict[str, float | None] = {}
    for idx, label in enumerate(LABELS):
        of_class = targets == idx
        out[label] = float((preds[of_class] == idx).mean()) if of_class.any() else None
    return out


def macro_f1(targets: np.ndarray, preds: np.ndarray) -> float:
    targets = np.asarray(targets)
    preds = np.asarray(preds)
    f1s = []
    for idx in range(len(LABELS)):
        tp = int(((preds == idx) & (targets == idx)).sum())
        fp = int(((preds == idx) & (targets != idx)).sum())
        fn = int(((preds != idx) & (targets == idx)).sum())
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(f1s))


def background_threat_fp_rate(targets: np.ndarray, preds: np.ndarray) -> float | None:
    """Fraction of true-background clips predicted as any threat class."""
    targets = np.asarray(targets)
    preds = np.asarray(preds)
    bg = targets == BACKGROUND_INDEX
    if not bg.any():
        return None
    return float((preds[bg] != BACKGROUND_INDEX).mean())


def class_vs_background_auc(probs: np.ndarray, targets: np.ndarray, class_index: int) -> float | None:
    """ROC-AUC of ``prob[class]`` separating that class from background clips.

    Threshold-free: measures whether the score even ranks threats above
    background, regardless of operating point. Returns None if either group is
    empty. Implemented directly (Mann-Whitney U / rank form) to stay torch- and
    sklearn-free for CI.
    """
    probs = np.asarray(probs, dtype=np.float64)
    targets = np.asarray(targets)
    pos = probs[targets == class_index, class_index]
    neg = probs[targets == BACKGROUND_INDEX, class_index]
    if pos.size == 0 or neg.size == 0:
        return None
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(order.size, dtype=np.float64)
    ranks[order] = np.arange(1, order.size + 1)
    # Average ranks within ties for a correct AUC on discrete scores.
    combined = np.concatenate([pos, neg])
    _tie_correct_ranks(combined, ranks)
    rank_sum_pos = ranks[: pos.size].sum()
    auc = (rank_sum_pos - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size)
    return float(auc)


def _tie_correct_ranks(values: np.ndarray, ranks: np.ndarray) -> None:
    order = np.argsort(values, kind="mergesort")
    sorted_vals = values[order]
    i = 0
    n = values.size
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        if j > i:
            avg = (ranks[order[i]] + ranks[order[j]]) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
        i = j + 1


# ---------------------------------------------------------------------------
# Bootstrap CIs
# ---------------------------------------------------------------------------

def bootstrap_ci(
    metric_fn: Callable[[np.ndarray], float | None],
    n: int,
    *,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, float | None]:
    """Clip-level bootstrap CI. ``metric_fn`` maps resampled indices -> scalar."""
    rng = np.random.default_rng(seed)
    point = metric_fn(np.arange(n))
    if point is None:
        return {"point": None, "lo": None, "hi": None, "n_boot": 0}
    samples = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        value = metric_fn(idx)
        if value is not None:
            samples.append(value)
    if not samples:
        return {"point": float(point), "lo": None, "hi": None, "n_boot": 0}
    lo, hi = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return {"point": float(point), "lo": float(lo), "hi": float(hi), "n_boot": len(samples)}
