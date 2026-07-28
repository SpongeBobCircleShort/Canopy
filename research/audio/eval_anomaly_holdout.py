"""Site-held-out evaluation CLI for the open-set anomaly detector.

Runs the full paper protocol against a holdout manifest (train/val on the
remaining sites, test on the held-out site) and writes a JSON report:

    python -m research.audio.eval_anomaly_holdout \
        --manifest data/audio/manifests/threat_manifest_forest_v1b_tambopata_holdout.csv \
        --embedder-model models/audio/threat_cnn_kaggle_augmented_v1 \
        --fp-target 0.10

The evaluation math lives in ``eval_anomaly.py`` (numpy only, CI-tested);
this driver adds the audio->embedding step with an on-disk cache so ablation
re-runs don't re-embed 17 GB of audio.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from research.audio import anomaly, eval_anomaly
from research.audio.eval_anomaly import BACKGROUND_LABEL
from research.audio.infer import AudioInferenceService
from research.audio.labels import canonical_label
from research.audio.manifest import read_manifest

DEFAULT_EMBEDDER = Path("models/audio/threat_cnn_kaggle_augmented_v1")
DEFAULT_CACHE_DIR = Path("data/audio/embeddings_cache")
DEFAULT_REPORT_DIR = Path("research/audio/reports")

# Closed-set reference: forest_v1b on the tambopata held-out test
# (research/audio/MODEL_STATUS.md, 2026-06-02). Shown alongside tambopata runs.
CLOSED_SET_TAMBOPATA_REFERENCE = {
    "model": "threat-cnn-forest-v1b-tambopata-holdout",
    "raw_argmax": {"chainsaw_recall": 0.976, "background_fp_rate": 0.500},
    "validation_calibrated": {"chainsaw_recall": 0.195, "background_fp_rate": 0.000},
}


def _resolve_path(manifest_path: Path, raw_path: str) -> Path:
    audio_path = Path(raw_path)
    if not audio_path.is_absolute():
        audio_path = manifest_path.parent / audio_path
    return audio_path


class PannsEmbedder:
    """AudioSet-pretrained CNN14 embedder (2048-d) via ``panns_inference``.

    Downloads the checkpoint to ~/panns_data on first use. Selected with
    ``--embedder-model panns``.
    """

    name = "panns_cnn14"
    SAMPLE_RATE = 32000

    def __init__(self) -> None:
        from panns_inference import AudioTagging

        self._model = AudioTagging(checkpoint_path=None, device="cpu")

    def embed(self, audio_path: Path) -> np.ndarray:
        import librosa

        audio, _ = librosa.load(str(audio_path), sr=self.SAMPLE_RATE, mono=True)
        _, embedding = self._model.inference(audio[None, :])
        return np.asarray(embedding[0], dtype=np.float64)


class CachedEmbedder:
    """Embeds clips through the selected encoder, caching per (embedder, manifest)."""

    def __init__(self, model_spec: str | Path, cache_dir: Path) -> None:
        self.model_spec = str(model_spec)
        self.is_panns = self.model_spec == "panns"
        self.is_birdnet = self.model_spec == "birdnet"
        if self.is_panns:
            name = PannsEmbedder.name
        elif self.is_birdnet:
            name = "birdnet_v2.4"
        else:
            name = Path(self.model_spec).name
        self.cache_dir = Path(cache_dir) / name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._service = None

    @property
    def service(self):
        if self._service is None:
            if self.is_panns:
                self._service = PannsEmbedder()
            elif self.is_birdnet:
                from research.audio.birdnet_embedder import BirdNETEmbedder
                self._service = BirdNETEmbedder()
            else:
                self._service = AudioInferenceService(Path(self.model_spec))
        return self._service

    def embed_manifest(self, manifest_path: Path, rows: list[dict[str, str]]) -> np.ndarray:
        cache_file = self.cache_dir / f"{manifest_path.stem}.npz"
        # Manifests overlap heavily (same raw RFCx clips), so read every cache
        # file for this embedder; write back only this manifest's rows.
        cached: dict[str, np.ndarray] = {}
        for sibling in sorted(self.cache_dir.glob("*.npz")):
            data = np.load(sibling, allow_pickle=False)
            cached.update(zip(data["paths"].tolist(), data["embeddings"]))
        paths = [str(_resolve_path(manifest_path, row["path"])) for row in rows]
        missing = [path for path in paths if path not in cached]
        if missing:
            print(f"Embedding {len(missing)} clips ({len(paths) - len(missing)} cached) ...", flush=True)
            for done, path in enumerate(missing, start=1):
                cached[path] = self.service.embed(Path(path)).astype(np.float64)
                if done % 100 == 0 or done == len(missing):
                    print(f"  {done}/{len(missing)}", flush=True)
            np.savez(
                cache_file,
                paths=np.array(paths),
                embeddings=np.array([cached[p] for p in paths]),
            )
        return np.array([cached[path] for path in paths])


def evaluate(args: argparse.Namespace) -> dict:
    manifest_path = Path(args.manifest)
    rows = read_manifest(manifest_path)
    labels = [canonical_label(row["label"]) for row in rows]
    splits = [row["split"] for row in rows]
    notes = [row.get("notes", "") for row in rows]

    embedder = CachedEmbedder(args.embedder_model, args.cache_dir)
    embeddings = embedder.embed_manifest(manifest_path, rows)

    masks = eval_anomaly.split_masks(labels, splits)
    labels_arr = np.asarray(labels)

    # Optional extra prototype sources (e.g. public-data positives for classes
    # the holdout manifest doesn't carry).
    train_pos_embeddings = embeddings[masks["train_positive"]]
    train_pos_labels = list(labels_arr[masks["train_positive"]])
    for extra in args.prototypes_manifest:
        extra_path = Path(extra)
        extra_rows = read_manifest(extra_path)
        extra_labels = [canonical_label(row["label"]) for row in extra_rows]
        keep = [label != BACKGROUND_LABEL for label in extra_labels]
        extra_embeddings = embedder.embed_manifest(extra_path, extra_rows)
        train_pos_embeddings = np.concatenate([train_pos_embeddings, extra_embeddings[np.array(keep)]])
        train_pos_labels.extend(label for label, kept in zip(extra_labels, keep) if kept)

    # 1. Fit on train.
    background = anomaly.fit_background(
        embeddings[masks["train_background"]],
        shrinkage=args.shrinkage,
        fp_target=args.fp_target,
    )
    if train_pos_labels:
        prototypes = anomaly.fit_prototypes(train_pos_embeddings, train_pos_labels)
    else:
        prototypes = anomaly.empty_prototypes(embeddings.shape[1])
    artifact = anomaly.build_artifact(
        background, prototypes, sim_threshold=args.sim_threshold, temperature=args.temperature
    )

    # 2. Calibrate the decision threshold on val background.
    val_bg_scores = eval_anomaly.score_all(embeddings[masks["val_background"]], artifact)["anomaly_score"]
    threshold = eval_anomaly.calibrate_threshold(val_bg_scores, args.fp_target)

    # Val diagnostics (closed-set protocol also reported val recall).
    val_mask = masks["val_background"] | masks["val_positive"]
    val_scored = eval_anomaly.score_all(embeddings[val_mask], artifact)
    val_point = eval_anomaly.operating_point(
        val_scored["anomaly_score"], val_scored["predicted_kind"], labels_arr[val_mask], threshold
    )

    # 3. Evaluate the held-out site test split.
    test_mask = masks["test_background"] | masks["test_positive"]
    test_labels = labels_arr[test_mask]
    test_embeddings = embeddings[test_mask]
    test_scored = eval_anomaly.score_all(test_embeddings, artifact)
    test_point = eval_anomaly.operating_point(
        test_scored["anomaly_score"], test_scored["predicted_kind"], test_labels, threshold
    )

    sweeps = {
        label: eval_anomaly.threshold_sweep(
            test_scored["anomaly_score"][test_labels == BACKGROUND_LABEL],
            test_scored["anomaly_score"][test_labels == label],
        )
        for label in sorted(set(test_labels) - {BACKGROUND_LABEL})
    }

    proto_curve = eval_anomaly.prototype_k_curve(
        background,
        train_pos_embeddings,
        train_pos_labels,
        test_embeddings,
        test_labels,
        threshold,
        ks=args.proto_ks,
        n_seeds=args.seeds,
        sim_threshold=args.sim_threshold,
        temperature=args.temperature,
    ) if train_pos_labels else []

    unknown_holdout = None
    if args.holdout_class:
        unknown_holdout = eval_anomaly.unknown_class_holdout(
            background,
            train_pos_embeddings,
            train_pos_labels,
            test_embeddings,
            test_labels,
            args.holdout_class,
            threshold,
            sim_threshold=args.sim_threshold,
            temperature=args.temperature,
        )

    heldout_sites = sorted({eval_anomaly.site_of(note) for note, m in zip(notes, test_mask) if m} - {""})
    report = {
        "manifest": str(manifest_path),
        "embedder_model": str(args.embedder_model),
        "heldout_sites": heldout_sites,
        "fp_target": args.fp_target,
        "sim_threshold": args.sim_threshold,
        "temperature": args.temperature,
        "shrinkage": args.shrinkage,
        "counts": {
            "train_background": int(masks["train_background"].sum()),
            "train_positive_by_class": dict(Counter(train_pos_labels)),
            "val_background": int(masks["val_background"].sum()),
            "val_positive": int(masks["val_positive"].sum()),
            "test_by_class": {k: int(v) for k, v in Counter(test_labels.tolist()).items()},
        },
        "calibrated_threshold": threshold,
        "val": val_point,
        "test": test_point,
        "test_threshold_sweeps": sweeps,
        "prototype_k_curve": proto_curve,
        "unknown_class_holdout": unknown_holdout,
    }
    if "tambopata" in heldout_sites:
        report["closed_set_reference"] = CLOSED_SET_TAMBOPATA_REFERENCE
    return report


def _print_summary(report: dict) -> None:
    sites = ", ".join(report["heldout_sites"]) or "(unknown)"
    print(f"\n## Open-set holdout evaluation — held-out site: {sites}")
    print(f"Embedder: {report['embedder_model']}")
    print(
        f"Calibrated anomaly threshold {report['calibrated_threshold']:.4f} "
        f"(val background FP <= {report['fp_target']})\n"
    )
    test = report["test"]
    print("| Model | Class | Flagged recall | Attributed recall | Background FP |")
    print("| --- | --- | ---: | ---: | ---: |")
    for label, metrics in test["classes"].items():
        print(
            f"| open-set (this run) | {label} | {metrics['flagged_recall']:.3f} "
            f"| {metrics['attributed_recall']:.3f} | {test['background_fp_rate']:.3f} |"
        )
    reference = report.get("closed_set_reference")
    if reference:
        calibrated = reference["validation_calibrated"]
        raw = reference["raw_argmax"]
        print(
            f"| closed-set forest_v1b (calibrated) | chainsaw | — "
            f"| {calibrated['chainsaw_recall']:.3f} | {calibrated['background_fp_rate']:.3f} |"
        )
        print(
            f"| closed-set forest_v1b (raw argmax) | chainsaw | — "
            f"| {raw['chainsaw_recall']:.3f} | {raw['background_fp_rate']:.3f} |"
        )
    for label, sweep in report["test_threshold_sweeps"].items():
        print(f"\nAUC ({label} vs background, anomaly score): {sweep['auc']:.3f}")
    if report["prototype_k_curve"]:
        print("\nPrototype-count curve (attributed recall, mean +/- std):")
        for entry in report["prototype_k_curve"]:
            parts = ", ".join(
                f"{label}: {m['attributed_recall_mean']:.3f}+/-{m['attributed_recall_std']:.3f}"
                for label, m in entry["classes"].items()
            )
            print(f"  k={entry['k']:>3}  {parts}")
    holdout = report.get("unknown_class_holdout")
    if holdout:
        print(
            f"\nUnknown-class holdout ({holdout['heldout_class']}; prototypes: "
            f"{holdout['remaining_prototypes'] or 'none'}): flagged {holdout['flagged_recall']:.3f}, "
            f"predicted unknown {holdout['predicted_unknown_of_flagged']}, "
            f"mean unknown mass {holdout['mean_unknown_mass_of_flagged']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Site-held-out evaluation of the open-set anomaly detector.")
    parser.add_argument("--manifest", type=Path, required=True, help="Holdout manifest (train/val/test splits)")
    parser.add_argument("--embedder-model", type=str, default=str(DEFAULT_EMBEDDER),
                        help="CNN embedder artifact dir, or 'panns' for the AudioSet-pretrained CNN14; "
                             "the default CNN is RFCx-free, so it is leakage-clean for every site holdout")
    parser.add_argument("--prototypes-manifest", action="append", default=[],
                        help="Extra positives manifest(s) for prototype classes the holdout manifest lacks")
    parser.add_argument("--fp-target", type=float, default=eval_anomaly.DEFAULT_FP_TARGET,
                        help="Background false-positive gate for threshold calibration (default 0.10)")
    parser.add_argument("--sim-threshold", type=float, default=0.5)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--shrinkage", type=float, default=0.1)
    parser.add_argument("--proto-ks", type=lambda s: tuple(int(k) for k in s.split(",")),
                        default=eval_anomaly.DEFAULT_PROTO_KS, help="Comma-separated k values (default 0,1,5,10,25)")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--holdout-class", default=None,
                        help="Run the honest-unknown experiment with this class removed from prototypes")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=None, help="JSON report path (default research/audio/reports/)")
    args = parser.parse_args()

    report = evaluate(args)

    out = args.out or DEFAULT_REPORT_DIR / f"anomaly_holdout_{Path(args.manifest).stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    _print_summary(report)
    print(f"\nFull report -> {out}")


if __name__ == "__main__":
    main()
