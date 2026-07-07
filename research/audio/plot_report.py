"""Render paper figures from an eval_anomaly_holdout JSON report.

    python -m research.audio.plot_report \
        --report research/audio/reports/anomaly_holdout_..._panns.json \
        --out-dir research/paper/aaai27-listening-without-labels/figures

Produces the prototype-count curve and the anomaly-score recall-vs-FP curve as
PDFs. matplotlib is imported lazily so importing this module stays cheap.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def plot_k_curve(report: dict, out_dir: Path) -> Path | None:
    import matplotlib.pyplot as plt

    curve = report.get("prototype_k_curve") or []
    if not curve:
        return None
    classes = sorted({label for entry in curve for label in entry["classes"]})
    ks = [entry["k"] for entry in curve]
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for label in classes:
        means = [entry["classes"].get(label, {}).get("attributed_recall_mean", float("nan")) for entry in curve]
        stds = [entry["classes"].get(label, {}).get("attributed_recall_std", 0.0) for entry in curve]
        ax.errorbar(ks, means, yerr=stds, marker="o", capsize=3, label=label)
    ax.set_xlabel("verified positives per class ($k$)")
    ax.set_ylabel("attributed recall")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    out = out_dir / "kcurve.pdf"
    fig.savefig(out)
    plt.close(fig)
    return out


def plot_roc(report: dict, out_dir: Path) -> Path | None:
    import matplotlib.pyplot as plt

    sweeps = report.get("test_threshold_sweeps") or {}
    if not sweeps:
        return None
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for label, sweep in sweeps.items():
        ax.plot(sweep["background_fp_rates"], sweep["recalls"], marker=".", ms=3,
                label=f"{label} (AUC={sweep['auc']:.2f})")
    ax.plot([0, 1], [0, 1], color="gray", ls="--", lw=0.8)
    ax.set_xlabel("background false-positive rate")
    ax.set_ylabel("flagged recall")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    out = out_dir / "roc.pdf"
    fig.savefig(out)
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Render figures from an eval report.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path,
                        default=Path("research/paper/aaai27-listening-without-labels/figures"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = json.loads(args.report.read_text())
    for producer in (plot_k_curve, plot_roc):
        result = producer(report, args.out_dir)
        print(f"wrote {result}" if result else f"skipped {producer.__name__} (no data)")


if __name__ == "__main__":
    main()
