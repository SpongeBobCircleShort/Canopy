# Listening Without Labels — AAAI-27 submission (AI for Social Impact track)

Open-set acoustic threat detection for forest conservation from background audio
alone. This directory holds the paper; the method, evaluation code, and fitted
artifacts live in `research/audio/` at the repo root.

## Status

Draft scaffold with all prose sections written. Every quantitative claim is
marked `PLACEHOLDER` and wired to a specific output of the evaluation harness —
fill from `research/audio/reports/*.json`.

## Build

The AAAI-27 author kit is **not** vendored here (fetch it from the AAAI-27
"Author Kit" page and drop `aaai2027.sty` / `aaai2027.bst` alongside `main.tex`).

```bash
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Reproducing the numbers

All commands run from the repo root.

```bash
# Primary head-to-head (held-out site: tambopata) — forest-CNN embedding
python -m research.audio.eval_anomaly_holdout \
  --manifest data/audio/manifests/threat_manifest_forest_v1b_tambopata_holdout.csv \
  --embedder-model models/audio/threat_cnn_kaggle_augmented_v1 \
  --fp-target 0.10 --holdout-class chainsaw

# Same, with the frozen AudioSet encoder (the paper's key comparison)
python -m research.audio.eval_anomaly_holdout \
  --manifest data/audio/manifests/threat_manifest_forest_v1b_tambopata_holdout.csv \
  --embedder-model panns --fp-target 0.10

# Additional leave-one-site-out folds
for site in warsi romania pooks; do
  python -m research.audio.build_forest_domain_manifest_v1 \
    --rfcx-heldout-site $site --chainsaw-background-only \
    --output data/audio/manifests/threat_manifest_forest_v1b_${site}_holdout.csv \
    --report-output data/audio/manifests/threat_manifest_forest_v1b_${site}_holdout_report.json
  python -m research.audio.eval_anomaly_holdout \
    --manifest data/audio/manifests/threat_manifest_forest_v1b_${site}_holdout.csv \
    --embedder-model panns --fp-target 0.10
done

# SNR-injection evaluation set (works today on RFCx background; swap in field
# background on delivery day)
# note the =form: --snrs values are negative, so argparse needs --snrs=...
python -m research.audio.inject_snr \
  --background-manifest data/audio/manifests/threat_manifest_forest_v1b.csv \
  --positives-manifest data/audio/manifests/kaggle_chainsaw_manifest.csv \
  --snrs=-10,-5,0,5 --per-snr 50 --out-dir data/audio/synthetic/snr_v1
python -m research.audio.eval_anomaly_holdout \
  --manifest data/audio/synthetic/snr_v1/manifest.csv --embedder-model panns
```

## Report -> paper mapping

| Placeholder | Source |
| --- | --- |
| Table 1 open-set rows | `reports/anomaly_holdout_*_*.json` -> `test.classes.chainsaw`, `test.background_fp_rate` |
| Embedding AUC comparison | `report["test_threshold_sweeps"][class]["auc"]` |
| Figure `kcurve` | `report["prototype_k_curve"]` |
| Honest-unknown numbers | `report["unknown_class_holdout"]` |
| Multi-site folds | one report per held-out site |

## Pre-submission checklist

- [ ] Replace every `PLACEHOLDER` in `sections/` and Table 1.
- [ ] Replace all `references.bib` stubs with **verified** citations (AAAI-27
      sanctions fabricated references — no LLM-invented bibliography entries).
- [ ] Drop in the AAAI-27 `.sty`/`.bst` and confirm the 7+2 page limit.
- [ ] Complete the AAAI reproducibility checklist.
- [ ] Confirm dataset licenses (RFCx CC BY-NC 4.0, Kaggle, FSC22) permit the
      intended code/data release.
- [ ] Register the abstract on OpenReview by **2026-07-21**; confirm the
      AISI-track deadline on its own CFP page (may differ from the main table).
