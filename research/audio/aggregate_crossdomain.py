"""Aggregate per-(model, site) cross-domain reports into the review tables.

Produces two markdown tables from research/audio/reports/crossdomain/*.json:
  1. Ablation ladder: each training recipe on a common held-out site, showing
     background-FP and chainsaw recall at the deployment-calibrated operating
     point (the reviewer's requested ablation format).
  2. Multi-site: the primary recipe across all held-out sites, with bootstrap
     CIs, showing findings are not tambopata-specific.

    python -m research.audio.aggregate_crossdomain
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPORT_DIR = Path("research/audio/reports/crossdomain")

# Training-recipe ladder, in intervention order (public data only, 0 RFCx clips).
LADDER = [
    ("threat_cnn_kaggle_balanced_v2", "baseline (balanced public)"),
    ("threat_cnn_kaggle_augmented_v1", "+ augmentation"),
    ("threat_cnn_expanded_hn_v3", "+ hard negatives"),
    ("threat_cnn_expanded_hn_v4", "+ more hard negatives"),
    ("threat_cnn_expanded_v5_hn", "+ expanded set"),
    ("threat_cnn_expanded_v5_hn_dcase", "+ DCASE machine negs"),
    ("threat_cnn_expanded_v6_bg_conservative", "+ conservative bg"),
]
SITES = ["tambopata", "warsi", "romania", "pooks"]


def _load(model: str, site: str) -> dict | None:
    f = REPORT_DIR / f"{model}__threat_manifest_forest_v1b_{site}_holdout.json"
    return json.loads(f.read_text()) if f.exists() else None


def _fmt(x, nd=3):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "n/a"


def ablation_table(site: str) -> str:
    lines = [
        f"### Ablation ladder on held-out site: {site} (deployment-calibrated)",
        "",
        "| Training recipe | Chainsaw recall | Background threat-FP | chainsaw-vs-bg AUC |",
        "| --- | ---: | ---: | ---: |",
    ]
    for model, desc in LADDER:
        r = _load(model, site)
        if not r:
            lines.append(f"| {desc} | missing | missing | missing |")
            continue
        cal = r["deployment_calibrated"]
        rec = cal["per_class_recall"].get("chainsaw")
        fp = cal["background_threat_fp_rate"]
        auc = r["class_vs_background_auc"].get("chainsaw", {}).get("point")
        lines.append(f"| {desc} | {_fmt(rec)} | {_fmt(fp)} | {_fmt(auc)} |")
    return "\n".join(lines)


def multisite_table(model: str) -> str:
    lines = [
        f"### Multi-site generalization: {model} (deployment-calibrated, 95% CI)",
        "",
        "| Held-out site | n_chain | n_bg | Chainsaw recall [CI] | Background threat-FP [CI] | AUC [CI] |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for site in SITES:
        r = _load(model, site)
        if not r:
            lines.append(f"| {site} | ? | ? | missing | missing | missing |")
            continue
        cal = r["deployment_calibrated"]
        rec_ci = cal["ci"]["chainsaw_recall"]
        fp_ci = cal["ci"]["background_threat_fp_rate"]
        auc = r["class_vs_background_auc"].get("chainsaw", {})
        nch = r["counts"].get("chainsaw", 0)
        nbg = r["counts"].get("background_unknown", 0)

        def ci_str(ci):
            if ci.get("point") is None:
                return "n/a"
            if ci.get("lo") is None:
                return _fmt(ci["point"])
            return f"{_fmt(ci['point'])} [{_fmt(ci['lo'])},{_fmt(ci['hi'])}]"

        lines.append(
            f"| {site} | {nch} | {nbg} | {ci_str(rec_ci)} | {ci_str(fp_ci)} | {ci_str(auc)} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate cross-domain reports into review tables.")
    parser.add_argument("--primary-model", default="threat_cnn_kaggle_augmented_v1")
    parser.add_argument("--ablation-site", default="warsi", help="Site with most support for the ablation table")
    parser.add_argument("--out", type=Path, default=Path("research/audio/reports/crossdomain/SUMMARY.md"))
    args = parser.parse_args()

    blocks = [
        "# Cross-site vetting — aggregated tables",
        "",
        "Public-trained models (0 RFCx clips) evaluated on held-out RFCx sites; "
        "pure inference, no contamination. Deployment thresholds are each model's "
        "own validation-calibrated thresholds.",
        "",
        multisite_table(args.primary_model),
        "",
        ablation_table(args.ablation_site),
        "",
    ]
    text = "\n".join(blocks)
    args.out.write_text(text)
    print(text)
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
