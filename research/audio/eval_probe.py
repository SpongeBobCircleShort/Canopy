"""Supervised leave-one-site-out probe over frozen embeddings (paper-grade).

For each held-out site we fit a logistic-regression probe on frozen embeddings of
the *training* sites (chainsaw vs background), calibrate a decision threshold on
*validation* background at a target false-positive rate, and evaluate on the
held-out site. This is the leakage-free, deployment-relevant counterpart to the
unsupervised open-set harness: it uses the chainsaw labels a real deployment has,
and tests generalization to an unseen site rather than to an unseen class.

Reports, per site and as n-weighted means:
  * clip-level AUROC with bootstrap 95% CIs (threshold-free),
  * clip-level recall at the val-calibrated threshold (with the realized test FP),
  * event-level recall: clips grouped back into recordings, since a chainsaw runs
    continuously and the operational unit is the event, not the 3-second clip.

The pure metric helpers are unit-tested; embeddings are pulled from the shared
cache produced by ``eval_anomaly_holdout``.

    python -m research.audio.eval_probe --embedders cnn,panns --fp-target 0.10
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from research.audio.eval_anomaly_holdout import CachedEmbedder, DEFAULT_CACHE_DIR
from research.audio.manifest import read_manifest

DEFAULT_SITES = ["tambopata", "romania", "pooks", "warsi"]
EMBEDDER_SPECS = {"cnn": "models/audio/threat_cnn_kaggle_augmented_v1", "panns": "panns", "birdnet": "birdnet"}
_SEG = re.compile(r"_\d+-\d+$")


# ---------------------------------------------------------------------------
# Pure metric helpers (unit-tested)
# ---------------------------------------------------------------------------

def recording_key(path: str) -> str:
    """Strip a trailing ``_<start>-<end>`` time window to recover the recording id.

    ``tambopata_2019_<uuid>_40-43.wav`` -> ``tambopata_2019_<uuid>``.
    """
    return _SEG.sub("", Path(path).stem)


def calibrate_threshold(background_scores: np.ndarray, fp_target: float) -> float:
    """Highest-recall threshold whose background exceedance is <= fp_target."""
    background_scores = np.asarray(background_scores, dtype=float)
    if background_scores.size == 0:
        return 0.0
    return float(np.quantile(background_scores, 1.0 - fp_target))


def recall_at_threshold(labels: np.ndarray, scores: np.ndarray, threshold: float) -> float:
    pos = np.asarray(scores)[np.asarray(labels) == 1]
    return float((pos > threshold).mean()) if pos.size else float("nan")


def false_positive_rate(labels: np.ndarray, scores: np.ndarray, threshold: float) -> float:
    bg = np.asarray(scores)[np.asarray(labels) == 0]
    return float((bg > threshold).mean()) if bg.size else float("nan")


def event_recall(paths: list[str], labels: np.ndarray, scores: np.ndarray, threshold: float, min_hits: int = 1) -> tuple[float, int]:
    """Group positive clips by recording; an event counts as detected when at least
    ``min_hits`` of its clips exceed the threshold."""
    groups: dict[str, list[float]] = defaultdict(list)
    for path, label, score in zip(paths, labels, scores):
        if label == 1:
            groups[recording_key(path)].append(float(score))
    if not groups:
        return float("nan"), 0
    detected = sum(1 for clip_scores in groups.values() if sum(s > threshold for s in clip_scores) >= min_hits)
    return detected / len(groups), len(groups)


def bootstrap_auroc_ci(labels: np.ndarray, scores: np.ndarray, n_boot: int = 1000, seed: int = 0) -> tuple[float, float]:
    from sklearn.metrics import roc_auc_score

    labels = np.asarray(labels)
    scores = np.asarray(scores)
    rng = np.random.default_rng(seed)
    n = len(labels)
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(labels[idx])) < 2:
            continue
        aucs.append(roc_auc_score(labels[idx], scores[idx]))
    if not aucs:
        return float("nan"), float("nan")
    lo, hi = np.percentile(aucs, [2.5, 97.5])
    return float(lo), float(hi)


def weighted_mean(values: list[float], weights: list[float]) -> float:
    pairs = [(v, w) for v, w in zip(values, weights) if not np.isnan(v)]
    total = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total if total else float("nan")


# ---------------------------------------------------------------------------
# Per-site evaluation
# ---------------------------------------------------------------------------

def evaluate_site(embedder: CachedEmbedder, manifest: Path, fp_target: float) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    rows = read_manifest(manifest)
    features = embedder.embed_manifest(manifest, rows)
    labels = np.array([1 if row["label"] == "chainsaw" else 0 for row in rows])
    split = np.array([row["split"] for row in rows])
    paths = [row["path"] for row in rows]
    train, val, test = split == "train", split == "val", split == "test"

    scaler = StandardScaler().fit(features[train])
    probe = LogisticRegression(max_iter=2000, class_weight="balanced").fit(scaler.transform(features[train]), labels[train])

    def score(mask: np.ndarray) -> np.ndarray:
        return probe.decision_function(scaler.transform(features[mask]))

    val_background = score(val)[labels[val] == 0]
    threshold = calibrate_threshold(val_background, fp_target)

    test_scores = score(test)
    test_labels = labels[test]
    test_paths = [p for p, m in zip(paths, test) if m]
    auroc = float(roc_auc_score(test_labels, test_scores)) if len(np.unique(test_labels)) > 1 else float("nan")
    lo, hi = bootstrap_auroc_ci(test_labels, test_scores)
    ev_recall, n_events = event_recall(test_paths, test_labels, test_scores, threshold)
    return {
        "n_test_chainsaw": int((test_labels == 1).sum()),
        "n_test_background": int((test_labels == 0).sum()),
        "auroc": auroc,
        "auroc_ci95": [lo, hi],
        "threshold": threshold,
        "clip_recall_at_fp": recall_at_threshold(test_labels, test_scores, threshold),
        "test_fp": false_positive_rate(test_labels, test_scores, threshold),
        "event_recall_at_fp": ev_recall,
        "n_events": n_events,
    }


def run(sites: list[str], embedders: list[str], fp_target: float, cache_dir: Path) -> dict:
    report: dict = {"fp_target": fp_target, "embedders": {}}
    for name in embedders:
        spec = EMBEDDER_SPECS.get(name, name)
        embedder = CachedEmbedder(spec, cache_dir)
        per_site = {}
        for site in sites:
            manifest = Path(f"data/audio/manifests/threat_manifest_forest_v1b_{site}_holdout.csv")
            per_site[site] = evaluate_site(embedder, manifest, fp_target)
        weights = [per_site[s]["n_test_chainsaw"] for s in sites]
        report["embedders"][name] = {
            "per_site": per_site,
            "weighted_auroc": weighted_mean([per_site[s]["auroc"] for s in sites], weights),
            "weighted_event_recall": weighted_mean([per_site[s]["event_recall_at_fp"] for s in sites], weights),
            "weighted_clip_recall": weighted_mean([per_site[s]["clip_recall_at_fp"] for s in sites], weights),
        }
    return report


def _print(report: dict) -> None:
    for name, block in report["embedders"].items():
        print(f"\n## {name}  (n-weighted: AUROC {block['weighted_auroc']:.3f}, "
              f"clip-recall {block['weighted_clip_recall']:.3f}, event-recall {block['weighted_event_recall']:.3f})")
        print(f"{'site':10s} {'n':>5s} {'AUROC [95% CI]':>22s} {'clipR@fp':>9s} {'eventR@fp':>10s} {'testFP':>7s}")
        for site, m in block["per_site"].items():
            ci = m["auroc_ci95"]
            print(f"{site:10s} {m['n_test_chainsaw']:>5d} "
                  f"{m['auroc']:.3f} [{ci[0]:.2f},{ci[1]:.2f}]".rjust(22)
                  + f" {m['clip_recall_at_fp']:>9.3f} {m['event_recall_at_fp']:>10.3f} {m['test_fp']:>7.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Supervised leave-one-site-out probe over frozen embeddings.")
    parser.add_argument("--sites", default=",".join(DEFAULT_SITES))
    parser.add_argument("--embedders", default="cnn,panns")
    parser.add_argument("--fp-target", type=float, default=0.10)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=Path("research/audio/reports/probe_holdout.json"))
    args = parser.parse_args()
    report = run(args.sites.split(","), args.embedders.split(","), args.fp_target, args.cache_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    _print(report)
    print(f"\nreport -> {args.out}")


if __name__ == "__main__":
    main()
