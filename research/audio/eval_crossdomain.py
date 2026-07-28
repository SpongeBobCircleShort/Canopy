"""Cross-site (public->forest) evaluation of the closed-set CNN classifier.

Runs a trained model on a held-out RFCx site's clips (which public-trained
models never saw) and reports, with clip-level bootstrap 95% CIs:

  * raw-argmax per-class recall, macro-F1, background threat-FP;
  * deployment-calibrated metrics using the model's own stored
    validation-calibrated thresholds (deployment_thresholds.json);
  * per-threat-class-vs-background ROC-AUC (threshold-free separability).

Softmax probabilities and targets are cached to npz so Phase-C plots (ROC/PR,
score distributions) reuse them without re-running inference.

    python -m research.audio.eval_crossdomain \
        --model models/audio/threat_cnn_kaggle_augmented_v1 \
        --manifest data/audio/manifests/threat_manifest_forest_v1b_warsi_holdout.csv \
        --split test

Only inference — no training, no contamination (verified: the public ladder
has zero RFCx clips). forest_v1/forest_v1b are excluded from cross-site claims
because they trained on every site.
"""
from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path

import numpy as np

from research.audio import crossdomain_metrics as cm
from research.audio.config import load_config
from research.audio.crossdomain_metrics import BACKGROUND_INDEX, LABELS, THREAT_INDICES
from research.audio.dataset import ThreatAudioDataset
from research.audio.evaluate import _feature_type
from research.audio.model import build_model, model_config_from_checkpoint

DEFAULT_CACHE = Path("research/audio/reports/crossdomain")


def _torch():
    import torch

    return torch


def infer_probs(model_dir: Path, manifest: Path, split: str) -> tuple[np.ndarray, np.ndarray]:
    torch = _torch()
    config = load_config(model_dir / "config.yaml")
    model_config = model_config_from_checkpoint(
        torch.load(model_dir / "model.pt", map_location="cpu", weights_only=False),
        config.get("model", {}),
    )
    dataset = ThreatAudioDataset(
        manifest,
        split=split,
        sample_rate=int(config["audio"]["sample_rate"]),
        clip_seconds=float(config["audio"]["clip_seconds"]),
        n_mels=int(config["audio"]["n_mels"]),
        feature_type=_feature_type(config.get("model", {})),
    )
    loader = torch.utils.data.DataLoader(dataset, batch_size=int(config["training"]["batch_size"]))
    checkpoint = torch.load(model_dir / "model.pt", map_location="cpu", weights_only=False)
    model = build_model(len(LABELS), model_config=model_config)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    probs: list[list[float]] = []
    targets: list[int] = []
    with torch.no_grad():
        for features, labels in loader:
            p = torch.softmax(model(features), dim=1)
            probs.extend(p.tolist())
            targets.extend(labels.tolist())
    return np.array(probs, dtype=np.float64), np.array(targets, dtype=int)


def _load_deployment_thresholds(model_dir: Path) -> dict[str, float]:
    path = model_dir / "deployment_thresholds.json"
    if path.exists():
        return json.loads(path.read_text()).get("thresholds", {})
    return {label: 0.5 for label in LABELS}


def _metrics_block(probs: np.ndarray, targets: np.ndarray, preds: np.ndarray, n_boot: int, seed: int) -> dict:
    def recall_on(idx_class, indices):
        t, p = targets[indices], preds[indices]
        of = t == idx_class
        return float((p[of] == idx_class).mean()) if of.any() else None

    def bgfp_on(indices):
        return cm.background_threat_fp_rate(targets[indices], preds[indices])

    block = {
        "macro_f1": cm.macro_f1(targets, preds),
        "per_class_recall": cm.per_class_recall(targets, preds),
        "background_threat_fp_rate": cm.background_threat_fp_rate(targets, preds),
        "ci": {
            "chainsaw_recall": cm.bootstrap_ci(
                partial(recall_on, LABELS.index("chainsaw")), targets.size, n_boot=n_boot, seed=seed
            ),
            "background_threat_fp_rate": cm.bootstrap_ci(bgfp_on, targets.size, n_boot=n_boot, seed=seed),
        },
    }
    return block


def evaluate(model_dir: Path, manifest: Path, split: str, n_boot: int, seed: int) -> dict:
    probs, targets = infer_probs(model_dir, manifest, split)

    raw_preds = cm.argmax_predictions(probs)
    thresholds = _load_deployment_thresholds(model_dir)
    cal_preds = cm.thresholded_predictions(probs, thresholds)

    def auc_on(class_index, indices):
        return cm.class_vs_background_auc(probs[indices], targets[indices], class_index)

    auc = {}
    for idx in THREAT_INDICES:
        point = cm.class_vs_background_auc(probs, targets, idx)
        if point is None:
            continue
        auc[LABELS[idx]] = cm.bootstrap_ci(partial(auc_on, idx), targets.size, n_boot=n_boot, seed=seed)

    counts = {LABELS[i]: int((targets == i).sum()) for i in range(len(LABELS)) if (targets == i).any()}
    return {
        "model": str(model_dir),
        "model_trained_on_rfcx": model_dir.name.startswith("threat_cnn_forest"),
        "manifest": str(manifest),
        "split": split,
        "n_clips": int(targets.size),
        "counts": counts,
        "deployment_thresholds": thresholds,
        "raw_argmax": _metrics_block(probs, targets, raw_preds, n_boot, seed),
        "deployment_calibrated": _metrics_block(probs, targets, cal_preds, n_boot, seed),
        "class_vs_background_auc": auc,
    }


def _print_summary(report: dict) -> None:
    site = Path(report["manifest"]).stem.replace("threat_manifest_forest_v1b_", "").replace("_holdout", "")
    print(f"\n== {Path(report['model']).name}  on site={site}  (n={report['n_clips']}, {report['counts']}) ==")
    for view in ("raw_argmax", "deployment_calibrated"):
        b = report[view]
        cs = b["per_class_recall"].get("chainsaw")
        ci = b["ci"]["chainsaw_recall"]
        fp = b["background_threat_fp_rate"]
        fpci = b["ci"]["background_threat_fp_rate"]
        cs_s = f"{cs:.3f}" if cs is not None else "n/a"
        fp_s = f"{fp:.3f}" if fp is not None else "n/a"
        ci_s = f"[{ci['lo']:.3f},{ci['hi']:.3f}]" if ci["lo"] is not None else ""
        fpci_s = f"[{fpci['lo']:.3f},{fpci['hi']:.3f}]" if fpci["lo"] is not None else ""
        print(f"  {view:22s} chainsaw_recall={cs_s} {ci_s}  macroF1={b['macro_f1']:.3f}  bgFP={fp_s} {fpci_s}")
    if report["class_vs_background_auc"].get("chainsaw"):
        a = report["class_vs_background_auc"]["chainsaw"]
        print(f"  chainsaw-vs-bg ROC-AUC = {a['point']:.3f} [{a['lo']:.3f},{a['hi']:.3f}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-site evaluation of a closed-set CNN classifier.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = evaluate(args.model, args.manifest, args.split, args.n_boot, args.seed)

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    site = Path(args.manifest).stem
    tag = f"{Path(args.model).name}__{site}"
    out = args.out or args.cache_dir / f"{tag}.json"
    out.write_text(json.dumps(report, indent=2))
    _print_summary(report)
    print(f"  report -> {out}")


if __name__ == "__main__":
    main()
