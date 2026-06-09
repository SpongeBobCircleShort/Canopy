"""Open-set acoustic anomaly detector core (numpy only, no torch/audio).

This module holds the math for Canopy's catch-all acoustic detector and is kept
deliberately free of torch/audio so it can be unit-tested in CI without the heavy
audio stack. The torch audio->embedding step lives in ``anomaly_infer.py`` and
``embeddings`` helpers; everything here operates on plain embedding vectors.

Two stages:

1. Background density (anomaly score). Fit a Gaussian over "normal forest
   background" embeddings and score a clip by its Mahalanobis distance. The raw
   distance is mapped to ``anomaly_score in [0, 1]`` via the empirical quantile
   of the background distances, so a score of 0.99 means "more unusual than 99%
   of background." The anomaly decision threshold is set from a background
   false-positive target, honoring the shared ``background FP < 0.10`` gate.

2. Open-set likelihood ("what does it seem to be"). Keep an L2-normalized
   prototype (mean embedding) per known class built from verified positives.
   Cosine similarity to prototypes becomes a distribution over the known classes
   plus a reserved ``unknown`` mass. With no prototypes every anomaly is honestly
   ``unknown``; as verified positives arrive per class, the labels light up.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ARTIFACT_VERSION = "anomaly-v1"
UNKNOWN_LABEL = "unknown"
_QUANTILE_POINTS = 1001  # resolution of the stored background-distance CDF


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------

def fit_background(
    embeddings: np.ndarray,
    *,
    shrinkage: float = 0.1,
    epsilon: float = 1e-6,
    fp_target: float = 0.01,
) -> dict[str, Any]:
    """Fit a shrunk-covariance Gaussian over background embeddings.

    ``fp_target`` is the fraction of background allowed above the anomaly
    threshold (e.g. 0.01 -> threshold at the 99th background percentile).
    """
    embeddings = _as_2d_float(embeddings)
    if embeddings.shape[0] < 2:
        raise ValueError("fit_background needs at least 2 background embeddings")
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage must be in [0, 1]")
    if not 0.0 < fp_target < 1.0:
        raise ValueError("fp_target must be in (0, 1)")

    mean = embeddings.mean(axis=0)
    cov = np.cov(embeddings, rowvar=False)
    cov = np.atleast_2d(cov)
    # Shrink toward a diagonal target for a well-conditioned, invertible matrix.
    diag_target = np.diag(np.diag(cov))
    cov_shrunk = (1.0 - shrinkage) * cov + shrinkage * diag_target
    cov_shrunk += epsilon * np.eye(cov_shrunk.shape[0])
    inv_cov = np.linalg.inv(cov_shrunk)

    distances = _mahalanobis(embeddings, mean, inv_cov)
    levels = np.linspace(0.0, 1.0, _QUANTILE_POINTS)
    quantile_distances = np.quantile(distances, levels)

    return {
        "mean": mean,
        "inv_cov": inv_cov,
        "quantile_levels": levels,
        "quantile_distances": quantile_distances,
        "anomaly_score_threshold": float(1.0 - fp_target),
        "fp_target": float(fp_target),
        "count": int(embeddings.shape[0]),
    }


def fit_prototypes(embeddings: np.ndarray, labels: list[str]) -> dict[str, Any]:
    """Build an L2-normalized mean prototype per known class label."""
    embeddings = _as_2d_float(embeddings)
    if embeddings.shape[0] != len(labels):
        raise ValueError("embeddings and labels must have the same length")
    unit = _l2_normalize(embeddings)
    proto_labels: list[str] = []
    vectors: list[np.ndarray] = []
    counts: list[int] = []
    for label in sorted(set(labels)):
        if label == UNKNOWN_LABEL:
            continue
        mask = np.array([lbl == label for lbl in labels])
        proto = _l2_normalize(unit[mask].mean(axis=0, keepdims=True))[0]
        proto_labels.append(label)
        vectors.append(proto)
        counts.append(int(mask.sum()))
    return {
        "labels": proto_labels,
        "vectors": np.array(vectors, dtype=np.float64) if vectors else np.zeros((0, embeddings.shape[1])),
        "counts": counts,
    }


def empty_prototypes(dim: int) -> dict[str, Any]:
    return {"labels": [], "vectors": np.zeros((0, dim)), "counts": []}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_embedding(
    embedding: np.ndarray,
    artifact: dict[str, Any],
    *,
    sim_threshold: float | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Score a single embedding -> anomaly score + open-set likelihoods."""
    background = artifact["background"]
    prototypes = artifact["prototypes"]
    sim_threshold = artifact.get("sim_threshold", 0.5) if sim_threshold is None else sim_threshold
    temperature = artifact.get("temperature", 0.1) if temperature is None else temperature

    emb = _as_1d_float(embedding)
    distance = float(_mahalanobis(emb[None, :], background["mean"], background["inv_cov"])[0])
    anomaly_score = float(
        np.interp(
            distance,
            background["quantile_distances"],
            background["quantile_levels"],
            left=0.0,
            right=1.0,
        )
    )
    is_anomaly = anomaly_score >= float(background["anomaly_score_threshold"])

    likelihoods = _open_set_likelihoods(emb, prototypes, sim_threshold, temperature)
    predicted_kind = max(likelihoods, key=likelihoods.get)
    return {
        "anomaly_score": anomaly_score,
        "is_anomaly": bool(is_anomaly),
        "distance": distance,
        "likelihoods": likelihoods,
        "predicted_kind": predicted_kind,
        "predicted_confidence": float(likelihoods[predicted_kind]),
    }


def _open_set_likelihoods(
    emb: np.ndarray,
    prototypes: dict[str, Any],
    sim_threshold: float,
    temperature: float,
) -> dict[str, float]:
    labels = list(prototypes["labels"])
    vectors = np.asarray(prototypes["vectors"], dtype=np.float64)
    if not labels or vectors.shape[0] == 0:
        return {UNKNOWN_LABEL: 1.0}

    unit = _l2_normalize(emb[None, :])[0]
    sims = vectors @ unit  # cosine similarity, both sides L2-normalized
    max_sim = float(sims.max())
    # How confidently does this look like *some* known class?
    denom = max(1.0 - sim_threshold, 1e-6)
    known_mass = float(np.clip((max_sim - sim_threshold) / denom, 0.0, 1.0))
    unknown_mass = 1.0 - known_mass

    weights = _softmax(sims / max(temperature, 1e-6))
    likelihoods = {label: float(known_mass * weight) for label, weight in zip(labels, weights)}
    likelihoods[UNKNOWN_LABEL] = unknown_mass
    return likelihoods


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def build_artifact(
    background: dict[str, Any],
    prototypes: dict[str, Any],
    *,
    embedder: dict[str, Any] | None = None,
    sim_threshold: float = 0.5,
    temperature: float = 0.1,
    model_version: str = ARTIFACT_VERSION,
) -> dict[str, Any]:
    return {
        "version": ARTIFACT_VERSION,
        "model_version": model_version,
        "embedder": embedder or {},
        "sim_threshold": float(sim_threshold),
        "temperature": float(temperature),
        "background": background,
        "prototypes": prototypes,
    }


def save_artifact(artifact: dict[str, Any], out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    background = artifact["background"]
    np.savez(
        out / "background_stats.npz",
        mean=background["mean"],
        inv_cov=background["inv_cov"],
        quantile_levels=background["quantile_levels"],
        quantile_distances=background["quantile_distances"],
    )
    prototypes = artifact["prototypes"]
    np.savez(
        out / "prototypes.npz",
        vectors=np.asarray(prototypes["vectors"], dtype=np.float64),
    )
    config = {
        "version": artifact.get("version", ARTIFACT_VERSION),
        "model_version": artifact.get("model_version", ARTIFACT_VERSION),
        "embedder": artifact.get("embedder", {}),
        "sim_threshold": float(artifact.get("sim_threshold", 0.5)),
        "temperature": float(artifact.get("temperature", 0.1)),
        "anomaly_score_threshold": float(background["anomaly_score_threshold"]),
        "fp_target": float(background.get("fp_target", 0.01)),
        "background_count": int(background.get("count", 0)),
        "prototype_labels": list(prototypes["labels"]),
        "prototype_counts": list(prototypes["counts"]),
    }
    (out / "detector_config.json").write_text(json.dumps(config, indent=2))
    return out


def load_artifact(model_dir: str | Path) -> dict[str, Any]:
    model_dir = Path(model_dir)
    config = json.loads((model_dir / "detector_config.json").read_text())
    bg = np.load(model_dir / "background_stats.npz")
    background = {
        "mean": bg["mean"],
        "inv_cov": bg["inv_cov"],
        "quantile_levels": bg["quantile_levels"],
        "quantile_distances": bg["quantile_distances"],
        "anomaly_score_threshold": float(config["anomaly_score_threshold"]),
        "fp_target": float(config.get("fp_target", 0.01)),
        "count": int(config.get("background_count", 0)),
    }
    proto_file = np.load(model_dir / "prototypes.npz")
    prototypes = {
        "labels": list(config.get("prototype_labels", [])),
        "vectors": proto_file["vectors"],
        "counts": list(config.get("prototype_counts", [])),
    }
    return build_artifact(
        background,
        prototypes,
        embedder=config.get("embedder", {}),
        sim_threshold=float(config.get("sim_threshold", 0.5)),
        temperature=float(config.get("temperature", 0.1)),
        model_version=config.get("model_version", ARTIFACT_VERSION),
    )


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

def _mahalanobis(points: np.ndarray, mean: np.ndarray, inv_cov: np.ndarray) -> np.ndarray:
    centered = points - mean
    quad = np.einsum("ij,jk,ik->i", centered, inv_cov, centered)
    return np.sqrt(np.clip(quad, 0.0, None))


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - values.max()
    exp = np.exp(shifted)
    return exp / exp.sum()


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


def _as_2d_float(array: np.ndarray) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError("expected a 2D (n_samples, dim) embedding array")
    return arr


def _as_1d_float(array: np.ndarray) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float64).reshape(-1)
    return arr
