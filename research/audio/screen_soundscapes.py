"""Screen candidate soundscapes so contaminated clips do not poison the neutral set.

Two detectors, run together for high recall (a clip flagged by either goes to
review):

1. Unsupervised, open-set (this module's core). Fit the anomaly background on the
   whole candidate corpus treated as "normal", then flag the clips that deviate.
   Because the corpus contains the very chainsaws/vehicles we are hunting, a naive
   single fit bakes them into "normal". So we do an ITERATIVE ROBUST REFIT: fit,
   drop the most anomalous fraction, refit on the cleaner remainder, repeat. Each
   round purifies "normal" and sharpens the outliers. This is exactly Canopy's
   open-set detector pointed at its own training data.

2. Supervised (optional). An AudioSet tagger (PANNs) that names known threat
   classes (chainsaw, engine, vehicle, gunshot, speech). Injected as a callable so
   this module stays torch-free and testable; the CLI wires a real one.

The pure scoring/partition logic here is numpy-only and unit-tested. The torch
embedder and the PANNs tagger live in the CLI wiring.

Example:

    python -m research.audio.screen_soundscapes \
        --embedder-model models/audio/threat_cnn_kaggle_augmented_v1 \
        --manifest data/audio/xeno_india_soundscapes/manifest.csv \
        --out-dir data/audio/xeno_india_screened \
        --threshold 0.9 --panns
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Callable

import numpy as np

from research.audio import anomaly
from research.audio.manifest import ManifestRow, read_manifest, write_manifest

BACKGROUND_LABEL = "background_unknown"
TaggerFn = Callable[[list[Path]], np.ndarray]


# ---------------------------------------------------------------------------
# Pure scoring logic (numpy only)
# ---------------------------------------------------------------------------

def _anomaly_scores(embeddings: np.ndarray, background: dict[str, Any]) -> np.ndarray:
    """Map each embedding to an anomaly score in [0, 1] against a fitted background."""
    distances = anomaly._mahalanobis(embeddings, background["mean"], background["inv_cov"])
    return np.interp(
        distances,
        background["quantile_distances"],
        background["quantile_levels"],
        left=0.0,
        right=1.0,
    )


def iterative_robust_background(
    embeddings: np.ndarray,
    *,
    drop_frac: float = 0.05,
    rounds: int = 3,
    fp_target: float = 0.01,
    shrinkage: float = 0.1,
    min_keep: int = 8,
) -> dict[str, Any]:
    """Fit a purified "normal forest" background and score every clip against it.

    Starting from all clips, each round fits the background on the current kept
    set, scores everything, and drops the most anomalous ``drop_frac`` from the
    kept set. The contaminating threats fall out over the rounds, so the final
    background is a cleaner "normal" and the final scores separate outliers better.

    Returns ``{"background", "scores", "kept_mask", "rounds_run"}`` where ``scores``
    is the final anomaly score per input clip and ``kept_mask`` marks the retained
    (inlier) clips.
    """
    embeddings = np.asarray(embeddings, dtype=np.float64)
    if embeddings.ndim != 2:
        raise ValueError("expected a 2D (n_clips, dim) embedding array")
    n = embeddings.shape[0]
    if n < min_keep:
        raise ValueError(f"need at least {min_keep} clips to screen, got {n}")
    if not 0.0 <= drop_frac < 0.5:
        raise ValueError("drop_frac must be in [0, 0.5)")

    kept = np.ones(n, dtype=bool)
    background = anomaly.fit_background(embeddings, fp_target=fp_target, shrinkage=shrinkage)
    rounds_run = 0
    for _ in range(rounds):
        background = anomaly.fit_background(embeddings[kept], fp_target=fp_target, shrinkage=shrinkage)
        scores = _anomaly_scores(embeddings, background)
        rounds_run += 1
        # Number to drop this round, relative to the currently kept set.
        n_kept = int(kept.sum())
        n_drop = int(np.floor(drop_frac * n_kept))
        if n_drop == 0 or n_kept - n_drop < min_keep:
            break
        kept_idx = np.flatnonzero(kept)
        worst = kept_idx[np.argsort(scores[kept_idx])[-n_drop:]]
        kept[worst] = False

    final_background = anomaly.fit_background(embeddings[kept], fp_target=fp_target, shrinkage=shrinkage)
    final_scores = _anomaly_scores(embeddings, final_background)
    return {
        "background": final_background,
        "scores": final_scores,
        "kept_mask": kept,
        "rounds_run": rounds_run,
    }


def ensemble_suspicion(
    anomaly_scores: np.ndarray,
    tagger_scores: np.ndarray | None = None,
    *,
    mode: str = "max",
    weight: float = 0.5,
) -> np.ndarray:
    """Combine the unsupervised anomaly score with an optional supervised threat
    score into one suspicion value in [0, 1].

    ``mode="max"`` (default) takes the elementwise max, biasing toward over-flagging
    for high recall. ``mode="weighted"`` blends them by ``weight`` on the anomaly
    score. With no tagger, the anomaly score is returned unchanged.
    """
    anomaly_scores = np.asarray(anomaly_scores, dtype=np.float64)
    if tagger_scores is None:
        return anomaly_scores
    tagger_scores = np.asarray(tagger_scores, dtype=np.float64)
    if tagger_scores.shape != anomaly_scores.shape:
        raise ValueError("anomaly_scores and tagger_scores must have the same shape")
    if mode == "max":
        return np.maximum(anomaly_scores, tagger_scores)
    if mode == "weighted":
        return weight * anomaly_scores + (1.0 - weight) * tagger_scores
    raise ValueError("mode must be 'max' or 'weighted'")


def partition_rows(
    rows: list[dict[str, str]],
    suspicion: np.ndarray,
    *,
    threshold: float,
) -> tuple[list[ManifestRow], list[ManifestRow]]:
    """Split manifest rows into (clean_neutral, flagged_for_review) by suspicion.

    Both keep ``background_unknown`` as the label (flagged clips are candidates, not
    confirmed threats — a human or the tagger decides), but the caller writes them
    to separate manifests so only the clean set feeds neutral training.
    """
    suspicion = np.asarray(suspicion, dtype=np.float64)
    if len(rows) != suspicion.shape[0]:
        raise ValueError("rows and suspicion must be the same length")
    clean: list[ManifestRow] = []
    flagged: list[ManifestRow] = []
    for row, score in zip(rows, suspicion):
        tag = "REVIEW" if score >= threshold else "clean"
        new_row = ManifestRow(
            path=row["path"],
            label=BACKGROUND_LABEL,
            source=row.get("source", "xeno_canto"),
            split=row.get("split", "train") or "train",
            duration_seconds=float(row["duration_seconds"]) if row.get("duration_seconds") else None,
            license=row.get("license", ""),
            notes=f"{row.get('notes', '')} suspicion:{score:.3f} {tag}".strip(),
        )
        (flagged if score >= threshold else clean).append(new_row)
    return clean, flagged


def ranked_review(rows: list[dict[str, str]], suspicion: np.ndarray) -> list[tuple[dict[str, str], float]]:
    """Rows paired with their suspicion, most to least suspicious."""
    pairs = list(zip(rows, np.asarray(suspicion, dtype=float).tolist()))
    return sorted(pairs, key=lambda pair: pair[1], reverse=True)


# ---------------------------------------------------------------------------
# Optional PANNs tagger (guarded import; torch + panns_inference)
# ---------------------------------------------------------------------------

# AudioSet class names PANNs emits that correspond to Canopy threats / human sound.
_THREAT_AUDIOSET_CLASSES = (
    "Chainsaw", "Engine", "Medium engine (mid frequency)", "Heavy engine (low frequency)",
    "Motor vehicle (road)", "Truck", "Car", "Gunshot, gunfire", "Machine gun",
    "Speech", "Chatter",
)


def load_panns_tagger() -> TaggerFn | None:
    """Build a PANNs threat tagger, or return None with guidance if unavailable."""
    try:
        import numpy as _np  # noqa: F401
        from panns_inference import AudioTagging, labels as panns_labels  # type: ignore
        import librosa  # type: ignore
    except Exception:  # noqa: BLE001
        print(
            "  PANNs tagger unavailable (need: pip install panns_inference librosa). "
            "Proceeding with the unsupervised anomaly detector only."
        )
        return None

    tagger = AudioTagging(checkpoint_path=None, device="cpu")
    threat_idx = [i for i, name in enumerate(panns_labels) if name in _THREAT_AUDIOSET_CLASSES]

    def _score(paths: list[Path]) -> np.ndarray:
        out = np.zeros(len(paths), dtype=np.float64)
        for i, path in enumerate(paths):
            try:
                wav, _ = librosa.load(str(path), sr=32000, mono=True)
                clipwise, _ = tagger.inference(wav[None, :])
                out[i] = float(clipwise[0, threat_idx].max()) if threat_idx else 0.0
            except Exception as exc:  # noqa: BLE001
                print(f"  tagger failed on {path}: {exc}")
        return out

    return _score


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def run(
    manifest: Path,
    embedder_model: Path,
    out_dir: Path,
    *,
    threshold: float = 0.9,
    drop_frac: float = 0.05,
    rounds: int = 3,
    tagger: TaggerFn | None = None,
    ensemble_mode: str = "max",
) -> dict[str, Path]:
    from research.audio.infer import AudioInferenceService

    rows = read_manifest(manifest)
    base = Path(manifest).parent
    paths = [base / row["path"] if not Path(row["path"]).is_absolute() else Path(row["path"]) for row in rows]

    embedder = AudioInferenceService(embedder_model)
    # Real-world audio is messy (mixed codecs, truncated files). Skip clips that
    # fail to decode/embed rather than crashing the whole run, and keep rows aligned.
    embeddings_list: list[np.ndarray] = []
    kept_rows: list[dict[str, str]] = []
    kept_paths: list[Path] = []
    skipped = 0
    for row, path in zip(rows, paths):
        try:
            embeddings_list.append(embedder.embed(path))
            kept_rows.append(row)
            kept_paths.append(path)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            print(f"  skip (undecodable): {path.name}: {exc}")
    if skipped:
        print(f"  {skipped} clips skipped (could not decode/embed), {len(kept_rows)} usable")
    rows, paths = kept_rows, kept_paths
    embeddings = np.array(embeddings_list, dtype=np.float64)

    result = iterative_robust_background(embeddings, drop_frac=drop_frac, rounds=rounds)
    tagger_scores = tagger(paths) if tagger is not None else None
    suspicion = ensemble_suspicion(result["scores"], tagger_scores, mode=ensemble_mode)

    clean, flagged = partition_rows(rows, suspicion, threshold=threshold)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_path = out_dir / "manifest_clean.csv"
    flagged_path = out_dir / "manifest_flagged.csv"
    review_path = out_dir / "review_ranked.csv"
    if clean:
        write_manifest(clean_path, clean)
    if flagged:
        write_manifest(flagged_path, flagged)

    with review_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "suspicion", "anomaly_score", "verdict"])
        anomaly_by_path = {row["path"]: score for row, score in zip(rows, result["scores"])}
        for row, score in ranked_review(rows, suspicion):
            writer.writerow([
                row["path"], f"{score:.4f}", f"{anomaly_by_path[row['path']]:.4f}",
                "REVIEW" if score >= threshold else "clean",
            ])

    print(
        f"Screened {len(rows)} clips ({result['rounds_run']} robust rounds).\n"
        f"  clean neutral: {len(clean)} -> {clean_path if clean else '(none)'}\n"
        f"  flagged for review: {len(flagged)} -> {flagged_path if flagged else '(none)'}\n"
        f"  ranked review list: {review_path}"
    )
    return {"clean": clean_path, "flagged": flagged_path, "review": review_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen candidate soundscapes for hidden threats before using as neutral.")
    parser.add_argument("--manifest", type=Path, required=True, help="Candidate background manifest (from fetch_xeno_canto)")
    parser.add_argument("--embedder-model", type=Path, required=True, help="CNN model artifact dir used to embed clips")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for the split manifests")
    parser.add_argument("--threshold", type=float, default=0.9, help="Suspicion cutoff for the review pile (default 0.9)")
    parser.add_argument("--drop-frac", type=float, default=0.05, help="Fraction dropped per robust refit round")
    parser.add_argument("--rounds", type=int, default=3, help="Robust refit rounds")
    parser.add_argument("--panns", action="store_true", help="Also run a PANNs AudioSet tagger (needs panns_inference)")
    args = parser.parse_args()
    tagger = load_panns_tagger() if args.panns else None
    run(
        args.manifest,
        args.embedder_model,
        args.out_dir,
        threshold=args.threshold,
        drop_frac=args.drop_frac,
        rounds=args.rounds,
        tagger=tagger,
    )


if __name__ == "__main__":
    main()
