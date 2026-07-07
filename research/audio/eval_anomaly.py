"""Site-held-out evaluation core for the open-set anomaly detector (numpy only).

This module holds the evaluation math and is kept free of torch/audio so it can
be unit-tested in CI without the heavy audio stack (same pattern as
``anomaly.py``). The audio->embedding step lives in the CLI driver
``eval_anomaly_holdout.py``.

Protocol — mirrors the closed-set forest_v1b evaluation in MODEL_STATUS.md so
the numbers are directly comparable:

1. Fit the background Gaussian on **train-split background** embeddings.
2. Build per-class prototypes from **train-split verified positives**.
3. Calibrate the anomaly-score decision threshold on **val-split background**
   so the validation background false-positive rate is <= ``fp_target``
   (default 0.10, the shared promotion-gate value).
4. Report flagged recall, background FP, and open-set attribution on the
   held-out-site **test split**.

Beyond the operating point, the report includes:

- a threshold sweep (recall vs background FP) with AUC, per positive class;
- a prototype-count curve: attribution recall vs. number of verified positives
  per class (k = 0 means no prototypes: everything is honestly ``unknown`` but
  flagging is unaffected);
- an unknown-class holdout: score a class with its prototype removed and
  measure where its likelihood mass goes.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

import numpy as np

from research.audio import anomaly
from research.audio.anomaly import UNKNOWN_LABEL

BACKGROUND_LABEL = "background_unknown"
DEFAULT_FP_TARGET = 0.10  # shared promotion-gate value (background FP < 0.10)
DEFAULT_PROTO_KS = (0, 1, 5, 10, 25)

_SITE_PATTERN = re.compile(r"site_id=([^;]+)")


# ---------------------------------------------------------------------------
# Manifest row helpers
# ---------------------------------------------------------------------------

def site_of(notes: str) -> str:
    """Extract the RFCx ``site_id`` from a manifest ``notes`` field ('' if absent)."""
    match = _SITE_PATTERN.search(notes or "")
    return match.group(1).strip() if match else ""


def split_masks(labels: Sequence[str], splits: Sequence[str]) -> dict[str, np.ndarray]:
    """Boolean masks for the six (split x background/positive) row groups."""
    labels_arr = np.asarray(labels)
    splits_arr = np.asarray(splits)
    is_background = labels_arr == BACKGROUND_LABEL
    masks: dict[str, np.ndarray] = {}
    for split in ("train", "val", "test"):
        in_split = splits_arr == split
        masks[f"{split}_background"] = in_split & is_background
        masks[f"{split}_positive"] = in_split & ~is_background
    return masks


# ---------------------------------------------------------------------------
# Scoring and calibration
# ---------------------------------------------------------------------------

def score_all(embeddings: np.ndarray, artifact: dict[str, Any]) -> dict[str, Any]:
    """Score every embedding; returns arrays plus per-row likelihood dicts."""
    scores: list[float] = []
    kinds: list[str] = []
    confidences: list[float] = []
    likelihoods: list[dict[str, float]] = []
    for row in np.asarray(embeddings, dtype=np.float64):
        result = anomaly.score_embedding(row, artifact)
        scores.append(result["anomaly_score"])
        kinds.append(result["predicted_kind"])
        confidences.append(result["predicted_confidence"])
        likelihoods.append(result["likelihoods"])
    return {
        "anomaly_score": np.array(scores),
        "predicted_kind": np.array(kinds),
        "predicted_confidence": np.array(confidences),
        "likelihoods": likelihoods,
    }


def calibrate_threshold(background_scores: np.ndarray, fp_target: float) -> float:
    """Smallest anomaly-score threshold with background FP <= ``fp_target``.

    Choosing the smallest such threshold maximizes recall subject to the FP
    gate, matching the closed-set calibration's ``max_background_fp_rate``
    constraint.
    """
    scores = np.asarray(background_scores, dtype=np.float64)
    if scores.size == 0:
        raise ValueError("calibrate_threshold needs at least one background score")
    if not 0.0 < fp_target < 1.0:
        raise ValueError("fp_target must be in (0, 1)")
    candidates = np.unique(scores)
    for threshold in candidates:
        if float(np.mean(scores >= threshold)) <= fp_target:
            return float(threshold)
    # No candidate meets the gate: step just above the max score (FP = 0).
    return float(np.nextafter(candidates[-1], np.inf))


def operating_point(
    scores: np.ndarray,
    predicted_kinds: np.ndarray,
    labels: Sequence[str],
    threshold: float,
) -> dict[str, Any]:
    """Flagging + attribution metrics at a fixed anomaly-score threshold."""
    scores = np.asarray(scores, dtype=np.float64)
    kinds = np.asarray(predicted_kinds)
    labels_arr = np.asarray(labels)
    flagged = scores >= threshold

    background = labels_arr == BACKGROUND_LABEL
    report: dict[str, Any] = {
        "threshold": float(threshold),
        "background_count": int(background.sum()),
        "background_fp_rate": float(flagged[background].mean()) if background.any() else None,
        "classes": {},
    }
    for label in sorted(set(labels_arr) - {BACKGROUND_LABEL}):
        of_class = labels_arr == label
        flagged_class = flagged & of_class
        n_class = int(of_class.sum())
        n_flagged = int(flagged_class.sum())
        attributed = int((flagged_class & (kinds == label)).sum())
        flagged_unknown = int((flagged_class & (kinds == UNKNOWN_LABEL)).sum())
        report["classes"][label] = {
            "count": n_class,
            "flagged_recall": n_flagged / n_class if n_class else None,
            "attributed_recall": attributed / n_class if n_class else None,
            "attributed_of_flagged": attributed / n_flagged if n_flagged else None,
            "unknown_of_flagged": flagged_unknown / n_flagged if n_flagged else None,
        }
    return report


def threshold_sweep(
    background_scores: np.ndarray,
    positive_scores: np.ndarray,
) -> dict[str, Any]:
    """Recall-vs-background-FP curve over all distinct thresholds, plus AUC."""
    bg = np.asarray(background_scores, dtype=np.float64)
    pos = np.asarray(positive_scores, dtype=np.float64)
    if bg.size == 0 or pos.size == 0:
        raise ValueError("threshold_sweep needs background and positive scores")
    thresholds = np.unique(np.concatenate([bg, pos]))
    fp_rates = np.array([float(np.mean(bg >= t)) for t in thresholds])
    recalls = np.array([float(np.mean(pos >= t)) for t in thresholds])
    order = np.argsort(fp_rates)
    # Anchor the curve at (0, 0) and (1, 1) for a proper AUC integral.
    fp_sorted = np.concatenate([[0.0], fp_rates[order], [1.0]])
    recall_sorted = np.concatenate([[0.0], recalls[order], [1.0]])
    trapezoid = getattr(np, "trapezoid", None) or np.trapz  # numpy<2 compat
    auc = float(trapezoid(recall_sorted, fp_sorted))
    return {
        "thresholds": thresholds.tolist(),
        "background_fp_rates": fp_rates.tolist(),
        "recalls": recalls.tolist(),
        "auc": auc,
    }


# ---------------------------------------------------------------------------
# Prototype ablations
# ---------------------------------------------------------------------------

def subsample_per_class(
    labels: Sequence[str],
    k: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Indices keeping at most ``k`` rows per class (all rows when k exceeds n)."""
    labels_arr = np.asarray(labels)
    keep: list[int] = []
    for label in sorted(set(labels_arr)):
        indices = np.flatnonzero(labels_arr == label)
        if k < indices.size:
            indices = rng.choice(indices, size=k, replace=False)
        keep.extend(int(i) for i in indices)
    return np.array(sorted(keep), dtype=int)


def prototype_k_curve(
    background: dict[str, Any],
    train_pos_embeddings: np.ndarray,
    train_pos_labels: Sequence[str],
    test_embeddings: np.ndarray,
    test_labels: Sequence[str],
    threshold: float,
    *,
    ks: Sequence[int] = DEFAULT_PROTO_KS,
    n_seeds: int = 5,
    sim_threshold: float = 0.5,
    temperature: float = 0.1,
) -> list[dict[str, Any]]:
    """Attribution recall vs. verified positives per class (mean +/- std over seeds).

    Only the prototypes are refit per (k, seed); the background density — and
    therefore flagging — is untouched, which is exactly the deployment story:
    ranger confirmations light labels up without touching the anomaly gate.
    """
    train_pos_embeddings = np.asarray(train_pos_embeddings, dtype=np.float64)
    results: list[dict[str, Any]] = []
    for k in ks:
        per_seed: dict[str, list[float]] = {}
        seeds = 1 if k == 0 or k >= len(train_pos_labels) else n_seeds
        for seed in range(seeds):
            rng = np.random.default_rng(seed)
            if k == 0:
                prototypes = anomaly.empty_prototypes(train_pos_embeddings.shape[1])
            else:
                keep = subsample_per_class(train_pos_labels, k, rng)
                prototypes = anomaly.fit_prototypes(
                    train_pos_embeddings[keep],
                    [train_pos_labels[i] for i in keep],
                )
            artifact = anomaly.build_artifact(
                background, prototypes, sim_threshold=sim_threshold, temperature=temperature
            )
            scored = score_all(test_embeddings, artifact)
            point = operating_point(scored["anomaly_score"], scored["predicted_kind"], test_labels, threshold)
            for label, metrics in point["classes"].items():
                per_seed.setdefault(label, []).append(metrics["attributed_recall"] or 0.0)
        results.append(
            {
                "k": int(k),
                "classes": {
                    label: {
                        "attributed_recall_mean": float(np.mean(values)),
                        "attributed_recall_std": float(np.std(values)),
                        "seeds": len(values),
                    }
                    for label, values in per_seed.items()
                },
            }
        )
    return results


def unknown_class_holdout(
    background: dict[str, Any],
    train_pos_embeddings: np.ndarray,
    train_pos_labels: Sequence[str],
    test_embeddings: np.ndarray,
    test_labels: Sequence[str],
    heldout_class: str,
    threshold: float,
    *,
    sim_threshold: float = 0.5,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Score ``heldout_class`` test clips with its prototype removed.

    The honest-unknown claim passes when flagged clips of the held-out class
    keep most likelihood mass on ``unknown`` instead of being misattributed to
    the remaining known classes.
    """
    train_pos_embeddings = np.asarray(train_pos_embeddings, dtype=np.float64)
    keep = np.asarray([label != heldout_class for label in train_pos_labels])
    if keep.any():
        prototypes = anomaly.fit_prototypes(
            train_pos_embeddings[keep],
            [label for label, kept in zip(train_pos_labels, keep) if kept],
        )
    else:
        prototypes = anomaly.empty_prototypes(train_pos_embeddings.shape[1])
    artifact = anomaly.build_artifact(
        background, prototypes, sim_threshold=sim_threshold, temperature=temperature
    )

    test_labels_arr = np.asarray(test_labels)
    of_class = test_labels_arr == heldout_class
    if not of_class.any():
        raise ValueError(f"no test rows with label '{heldout_class}'")
    scored = score_all(np.asarray(test_embeddings, dtype=np.float64)[of_class], artifact)
    flagged = scored["anomaly_score"] >= threshold

    kinds = scored["predicted_kind"][flagged]
    unknown_mass = np.array([lik.get(UNKNOWN_LABEL, 0.0) for lik, f in zip(scored["likelihoods"], flagged) if f])
    misattributions = {
        label: float(np.mean(kinds == label))
        for label in sorted(set(kinds) - {UNKNOWN_LABEL})
    }
    return {
        "heldout_class": heldout_class,
        "remaining_prototypes": list(prototypes["labels"]),
        "count": int(of_class.sum()),
        "flagged_recall": float(flagged.mean()),
        "predicted_unknown_of_flagged": float(np.mean(kinds == UNKNOWN_LABEL)) if kinds.size else None,
        "mean_unknown_mass_of_flagged": float(unknown_mass.mean()) if unknown_mass.size else None,
        "misattributed_of_flagged": misattributions,
    }
