# Listening Without Labels — AAAI-27 submission (AI for Social Impact track)

Open-set acoustic threat detection for forest conservation from background audio
alone. This directory holds the paper; the method, evaluation code, and fitted
artifacts live in `research/audio/` at the repo root.

## Status

Complete draft. All quantitative claims regenerated from scratch (2026-07-28) and
traced to committed report files; see the mapping below. Bibliography contains
verified citations only.

## Build

`aaai2027.sty` and `aaai2027.bst` are vendored from the AAAI-27 author kit; the
preamble matches the official template (natbib, no forbidden font packages,
`secnumdepth 2` so section cross-references resolve).

```bash
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

No TeX toolchain is required to iterate on content — or upload the folder to
Overleaf to compile with zero local install. `ReproducibilityChecklist.tex` is
filled and compiles standalone (`pdflatex ReproducibilityChecklist`); it is
wired as a commented optional `\input` in `main.tex`.

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

All numbers regenerated from scratch on 2026-07-28. Every value below traces to a
committed report file.

Diagnosis (Sec. 3):

| Element | Source |
| --- | --- |
| Table `diag-multisite` | `reports/crossdomain/threat_cnn_kaggle_augmented_v1__*_holdout.json` |
| Table `diag-ablation` | `reports/crossdomain/SUMMARY.md` |
| Table `diag-probe` + Fig `pca` | `reports/represent_probe.json`; `figures/pca_*.pdf` |
| In-domain 0.907 accuracy | `models/audio/threat_cnn_kaggle_augmented_v1/test_metrics.json` |

Experiments (Sec. 5):

| Element | Source |
| --- | --- |
| Table `headline`, `folds` | `reports/holdout_{site}_{cnn,panns}.json` |
| Table `probe` + Fig `transfer` | `reports/probe_holdout.json` |
| Fig `kcurve` | `reports/holdout_tambopata_panns.json` -> `prototype_k_curve` |
| BirdNET calibration failure | `reports/holdout_{site}_birdnet.json` (recall 0.000, AUC to 0.821) |
| Honest-unknown | `reports/holdout_*.json` -> `unknown_class_holdout` |

Regenerate everything:

```bash
for emb in cnn panns birdnet; do for site in tambopata warsi romania pooks; do
  python -m research.audio.eval_anomaly_holdout \
    --manifest data/audio/manifests/threat_manifest_forest_v1b_${site}_holdout.csv \
    --embedder-model $emb --fp-target 0.10 --holdout-class chainsaw \
    --out research/audio/reports/holdout_${site}_${emb}.json
done; done
python -m research.audio.eval_probe --embedders cnn,panns,birdnet --fp-target 0.10
python -m research.audio.represent_probe --panns --min-site-count 20 --plot
python -m research.audio.plot_probe && python -m research.audio.plot_report \
  --report research/audio/reports/holdout_tambopata_panns.json
```

## Pre-submission checklist

- [x] All `PLACEHOLDER` values replaced with re-run numbers.
- [x] `references.bib` contains verified citations only (no invented entries).
- [x] AAAI-27 `.sty`/`.bst` vendored; preamble reconciled to the official template.
- [ ] Confirm the 7+2 page limit after compiling.
- [ ] Add remaining citations for the conservation-acoustics and DCASE paragraphs.
- [x] Complete the AAAI reproducibility checklist (`ReproducibilityChecklist.tex`).
- [ ] Confirm dataset licenses (RFCx CC BY-NC 4.0, Kaggle, FSC22) permit the
      intended code/data release.
- [ ] Register the abstract on OpenReview by **2026-07-21**; confirm the
      AISI-track deadline on its own CFP page (may differ from the main table).
