"""Fit a Canopy open-set anomaly detector from background (and optional positives).

Background-only is enough to ship: it fits the "normal forest" density used for
the anomaly score. Passing a positives manifest additionally builds per-class
prototypes for the "what does it seem to be" likelihood. Re-running with more
verified positives is how new threat classes light up over time -- no full
retrain of the embedder is required.

Example:

    python -m research.audio.fit_anomaly \
        --embedder-model models/audio/threat_cnn_kaggle_augmented_v1 \
        --background-manifest data/audio/manifests/india_background_v1.csv \
        --out models/audio/anomaly_v1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from research.audio import anomaly
from research.audio.infer import AudioInferenceService
from research.audio.labels import canonical_label
from research.audio.manifest import read_manifest

BACKGROUND_LABEL = "background_unknown"


def _resolve_path(manifest_path: Path, raw_path: str) -> Path:
    audio_path = Path(raw_path)
    if not audio_path.is_absolute():
        audio_path = manifest_path.parent / audio_path
    return audio_path


def _embed_manifest(embedder: AudioInferenceService, manifest_path: Path) -> tuple[np.ndarray, list[str]]:
    rows = read_manifest(manifest_path)
    embeddings: list[np.ndarray] = []
    labels: list[str] = []
    for row in rows:
        embeddings.append(embedder.embed(_resolve_path(manifest_path, row["path"])))
        labels.append(canonical_label(row["label"]))
    return np.array(embeddings, dtype=np.float64), labels


def fit(
    embedder_model: Path,
    background_manifest: Path,
    out_dir: Path,
    *,
    positives_manifest: Path | None = None,
    fp_target: float = 0.01,
    sim_threshold: float = 0.5,
    temperature: float = 0.1,
) -> Path:
    embedder = AudioInferenceService(embedder_model)

    background_embeddings, _ = _embed_manifest(embedder, background_manifest)
    background = anomaly.fit_background(background_embeddings, fp_target=fp_target)

    dim = background_embeddings.shape[1]
    if positives_manifest is not None:
        pos_embeddings, pos_labels = _embed_manifest(embedder, positives_manifest)
        # Background clips carry no positive class signal; drop them from prototypes.
        keep = [label != BACKGROUND_LABEL for label in pos_labels]
        if any(keep):
            pos_embeddings = pos_embeddings[np.array(keep)]
            pos_labels = [label for label, k in zip(pos_labels, keep) if k]
            prototypes = anomaly.fit_prototypes(pos_embeddings, pos_labels)
        else:
            prototypes = anomaly.empty_prototypes(dim)
    else:
        prototypes = anomaly.empty_prototypes(dim)

    artifact = anomaly.build_artifact(
        background,
        prototypes,
        embedder={
            "model_dir": str(embedder_model),
            "model_version": embedder.checkpoint.get("artifact", {}).get("model_version"),
            "architecture": str(embedder.model_config.get("architecture", "cnn")),
            "embedding_dim": int(dim),
        },
        sim_threshold=sim_threshold,
        temperature=temperature,
    )
    out = anomaly.save_artifact(artifact, out_dir)
    print(
        f"Fitted anomaly detector -> {out}\n"
        f"  background clips: {background['count']}\n"
        f"  prototype classes: {prototypes['labels'] or '(none — all anomalies will be unknown)'}"
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit a Canopy open-set acoustic anomaly detector.")
    parser.add_argument("--embedder-model", type=Path, required=True, help="CNN model artifact dir used to embed clips")
    parser.add_argument("--background-manifest", type=Path, required=True, help="Manifest of background clips")
    parser.add_argument("--positives-manifest", type=Path, default=None, help="Optional manifest of verified positives")
    parser.add_argument("--out", type=Path, required=True, help="Output anomaly artifact directory")
    parser.add_argument("--fp-target", type=float, default=0.01, help="Background false-positive target (default 0.01)")
    parser.add_argument("--sim-threshold", type=float, default=0.5, help="Cosine similarity threshold for a known class")
    parser.add_argument("--temperature", type=float, default=0.1, help="Softmax temperature over known-class similarities")
    args = parser.parse_args()
    fit(
        args.embedder_model,
        args.background_manifest,
        args.out,
        positives_manifest=args.positives_manifest,
        fp_target=args.fp_target,
        sim_threshold=args.sim_threshold,
        temperature=args.temperature,
    )


if __name__ == "__main__":
    main()
