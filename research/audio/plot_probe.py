"""Render the label-free vs label-rich comparison figure from verified reports.

Reads the supervised-probe report and the open-set holdout reports and draws
per-site AUROC by embedding, which is the paper's central comparison: the
representation, not the detector head, governs cross-site transfer.

    python -m research.audio.plot_probe
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SITES = ["tambopata", "warsi", "romania", "pooks"]
EMBEDDERS = ["cnn", "panns", "birdnet"]
LABELS = {"cnn": "site-trained CNN", "panns": "AudioSet CNN14", "birdnet": "BirdNET V2.4"}


def load(probe_path: Path, reports_dir: Path):
    probe = json.loads(probe_path.read_text())["embedders"]
    openset = {}
    for emb in EMBEDDERS:
        for site in SITES:
            f = reports_dir / f"holdout_{site}_{emb}.json"
            if f.exists():
                d = json.loads(f.read_text())
                openset[(emb, site)] = d["test_threshold_sweeps"]["chainsaw"]["auc"]
    return probe, openset


def plot(probe, openset, out: Path) -> Path:
    import matplotlib.pyplot as plt
    import numpy as np

    # Single-column AAAI figure: keep type >= 7pt at final size, no rotated ticks.
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9,
                         "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8.5})
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.5), sharey=True)
    width = 0.26
    x = np.arange(len(SITES))

    panels = [
        (axes[0], "Label-free (background-only)", lambda e, s: openset.get((e, s), float("nan"))),
        (axes[1], "Label-rich (supervised probe)",
         lambda e, s: probe.get(e, {}).get("per_site", {}).get(s, {}).get("auroc", float("nan"))),
    ]
    for ax, title, getter in panels:
        for i, emb in enumerate(EMBEDDERS):
            ax.bar(x + (i - 1) * width, [getter(emb, s) for s in SITES], width, label=LABELS[emb])
        ax.axhline(0.5, color="0.35", ls="--", lw=0.8)
        ax.set_title(title)
        ax.set_xticks(x)
        # Horizontal labels: site names are short enough to fit unrotated.
        ax.set_xticklabels(SITES)
        ax.set_ylim(0, 1.05)
        ax.tick_params(axis="x", length=0, pad=3)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("chainsaw-vs-background AUC")
    axes[0].annotate("chance", xy=(len(SITES) - 0.55, 0.5), xytext=(0, 3),
                     textcoords="offset points", fontsize=6.5, color="0.35")
    axes[1].legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3,
                   handlelength=1.2, columnspacing=1.2)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot label-free vs label-rich transfer.")
    parser.add_argument("--probe", type=Path, default=Path("research/audio/reports/probe_holdout.json"))
    parser.add_argument("--reports-dir", type=Path, default=Path("research/audio/reports"))
    parser.add_argument("--out", type=Path,
                        default=Path("research/paper/aaai27-listening-without-labels/figures/transfer.pdf"))
    args = parser.parse_args()
    probe, openset = load(args.probe, args.reports_dir)
    print("wrote", plot(probe, openset, args.out))


if __name__ == "__main__":
    main()
