"""Representation analysis: does the embedding encode the event, or the site?

Tests H2 ("the classifier learned *where*, not *what*") on cached embeddings:

  1. Linear-probe comparison. Fit two logistic-regression probes on the same
     frozen embeddings: one predicting event class, one predicting recording
     site. If site is at least as predictable as class, the representation is
     dominated by site identity, which is exactly why it fails to transfer.
  2. Low-dimensional structure. PCA (and optional t-SNE) coordinates colored by
     class and by site, so clustering-by-site vs clustering-by-class is visible.

Compares the supervised forest CNN embedding against the frozen AudioSet CNN14
embedding under identical probes. Uses sklearn (installed); no torch needed if
embeddings are already cached by eval_anomaly_holdout / a PANNs cache.

    python -m research.audio.represent_probe \
        --manifest data/audio/manifests/threat_manifest_forest_v1b.csv \
        --cnn-model models/audio/threat_cnn_kaggle_augmented_v1 --panns
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np

from research.audio.labels import canonical_label

_SITE = re.compile(r"site_id=([^;]+)")


def _rows(manifest: Path) -> list[dict]:
    with open(manifest) as f:
        return list(csv.DictReader(f))


def _site(notes: str) -> str:
    m = _SITE.search(notes or "")
    return m.group(1).strip() if m else ""


def _cv_probe(X: np.ndarray, y: np.ndarray, seed: int = 0) -> dict:
    """Balanced-accuracy of a logistic-regression probe, 5-fold stratified CV."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    classes, counts = np.unique(y, return_counts=True)
    if classes.size < 2:
        return {"balanced_accuracy": None, "n_classes": int(classes.size), "note": "only one label present"}
    n_splits = int(min(5, counts.min()))
    if n_splits < 2:
        return {"balanced_accuracy": None, "n_classes": int(classes.size), "note": "a label has <2 samples"}
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    scores = []
    for tr, te in skf.split(X, y):
        scaler = StandardScaler().fit(X[tr])
        clf = LogisticRegression(max_iter=2000, class_weight="balanced")
        clf.fit(scaler.transform(X[tr]), y[tr])
        scores.append(balanced_accuracy_score(y[te], clf.predict(scaler.transform(X[te]))))
    return {
        "balanced_accuracy": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "n_splits": n_splits,
        "n_classes": int(classes.size),
        "chance": float(1.0 / classes.size),
    }


def _embed(rows, manifest, cnn_model, use_panns):
    """Return {name: (embeddings, keep_mask)} for each requested embedder."""
    from research.audio.eval_anomaly_holdout import CachedEmbedder

    paths = [r["path"] if Path(r["path"]).is_absolute() else str(manifest.parent / r["path"]) for r in rows]
    out = {}
    if cnn_model:
        emb = CachedEmbedder(str(cnn_model), Path("data/audio/embeddings_cache"))
        out[f"cnn:{Path(cnn_model).name}"] = np.array([emb.service.embed(Path(p)) for p in paths], dtype=np.float64)
    if use_panns:
        emb = CachedEmbedder("panns", Path("data/audio/embeddings_cache"))
        out["panns_cnn14"] = np.array([emb.service.embed(Path(p)) for p in paths], dtype=np.float64)
    return out, paths


def analyze(args) -> dict:
    manifest = Path(args.manifest)
    rows = _rows(manifest)
    # Restrict to labeled forest clips with a known site (the transfer question).
    rows = [r for r in rows if _site(r.get("notes", ""))]
    # Drop rare sites so the site probe's stratified CV is well-defined.
    if args.min_site_count:
        site_counts: dict[str, int] = {}
        for r in rows:
            site_counts[_site(r["notes"])] = site_counts.get(_site(r["notes"]), 0) + 1
        keep_sites = {s for s, c in site_counts.items() if c >= args.min_site_count}
        rows = [r for r in rows if _site(r["notes"]) in keep_sites]
    if args.max_per_group:
        # cap per (site,label) so neither probe is dominated by one cell
        seen: dict[tuple, int] = {}
        capped = []
        for r in rows:
            key = (_site(r["notes"]), canonical_label(r["label"]))
            if seen.get(key, 0) >= args.max_per_group:
                continue
            seen[key] = seen.get(key, 0) + 1
            capped.append(r)
        rows = capped

    labels = np.array([canonical_label(r["label"]) for r in rows])
    sites = np.array([_site(r["notes"]) for r in rows])

    embeddings, _ = _embed(rows, manifest, args.cnn_model, args.panns)
    result = {
        "manifest": str(manifest),
        "n_clips": len(rows),
        "n_sites": int(np.unique(sites).size),
        "class_distribution": {k: int(v) for k, v in zip(*np.unique(labels, return_counts=True))},
        "site_distribution": {k: int(v) for k, v in zip(*np.unique(sites, return_counts=True))},
        "probes": {},
    }
    for name, X in embeddings.items():
        result["probes"][name] = {
            "predict_class": _cv_probe(X, labels, args.seed),
            "predict_site": _cv_probe(X, sites, args.seed),
        }
        if args.plot:
            _plot_embedding(X, labels, sites, name, Path(args.plot_dir))
    return result


def _plot_embedding(X, labels, sites, name, out_dir):
    """One column-width figure with class- and site-colored PCA side by side.

    Drawn at the AAAI single-column width so LaTeX includes it at 1:1 and the
    tick/legend type is not shrunk by downscaling.
    """
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    plt.rcParams.update({"font.size": 7, "axes.titlesize": 7.5, "legend.fontsize": 5.6})
    out_dir.mkdir(parents=True, exist_ok=True)
    coords = PCA(n_components=2, random_state=0).fit_transform(StandardScaler().fit_transform(X))

    fig, axes = plt.subplots(1, 2, figsize=(3.3, 1.85))
    for ax, (by, values) in zip(axes, (("event class", labels), ("recording site", sites))):
        for v in sorted(set(values)):
            m = values == v
            ax.scatter(coords[m, 0], coords[m, 1], s=4, alpha=0.6, linewidths=0, label=str(v))
        ax.set_title(f"by {by}")
        ax.set_xticks([]); ax.set_yticks([])
        leg = ax.legend(markerscale=2.0, ncol=2, handletextpad=0.1,
                        columnspacing=0.4, labelspacing=0.2, loc="upper left",
                        bbox_to_anchor=(-0.02, 1.02), frameon=True, framealpha=0.92,
                        facecolor="white", edgecolor="none", borderpad=0.25)
        leg.set_zorder(5)
    fig.tight_layout(w_pad=0.6)
    safe = name.replace(":", "_").replace("/", "_")
    out = out_dir / f"pca_{safe}.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Class-vs-site linear-probe representation analysis.")
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/manifests/threat_manifest_forest_v1b.csv"))
    parser.add_argument("--cnn-model", type=Path, default=Path("models/audio/threat_cnn_kaggle_augmented_v1"))
    parser.add_argument("--panns", action="store_true", help="Also probe the frozen AudioSet CNN14 embedding")
    parser.add_argument("--max-per-group", type=int, default=0, help="Cap clips per (site,label) cell (0 = no cap)")
    parser.add_argument("--min-site-count", type=int, default=20, help="Drop sites with fewer than this many clips")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--plot-dir", default="research/paper/aaai27-listening-without-labels/figures")
    parser.add_argument("--out", type=Path, default=Path("research/audio/reports/represent_probe.json"))
    args = parser.parse_args()

    result = analyze(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
