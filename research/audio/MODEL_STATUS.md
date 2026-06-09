# Canopy Audio Model Status

## 2026-06-10: Pivot to open-set anomaly detection

Following the forest_v1b finding below (the closed-set classifier does not learn
a deployable cross-site boundary), the acoustic path is now a **catch-all
open-set anomaly detector**: score deviation from normal forest background, then
report a likelihood of what the anomaly seems to be, including `unknown`.

Why: the anomaly score is learned from background alone, so it ships on incoming
field background (e.g. the Indian forestry background delivery) with no positives
required; per-class "what is it" prototypes light up incrementally as verified
positives arrive — no full retrain. Design and fit/serve workflow:
[../../docs/anomaly-detection.md](../../docs/anomaly-detection.md). Core math:
`research/audio/anomaly.py`; fit CLI: `research/audio/fit_anomaly.py`.

The promotion gate is unchanged: acoustic confidence re-enters fusion scoring
only after chainsaw recall > 0.70 and background FP < 0.10 on held-out clips from
at least 3 sites. The closed-set CNN is retained as the embedding backbone and
for research only.

## 2026-06-02: forest_v1b Tambopata Held-Out Evaluation

Purpose: measure whether the RFCx-based chainsaw detector generalizes to a site that never appears in train or validation.

Setup:

- Model: `threat-cnn-forest-v1b-tambopata-holdout`
- Manifest: `data/audio/manifests/threat_manifest_forest_v1b_tambopata_holdout.csv`
- Scope: chainsaw vs. background only; gunshot, vehicle, and fire were excluded from this run.
- Held-out site: all RFCx `tambopata` clips were reserved for test only.
- Test support: 113 tambopata clips, with 41 chainsaw and 72 background.
- Train/validation leakage check: 0 tambopata clips in train or validation.
- Best checkpoint: epoch 15.

Results on tambopata-only test:

| Metric view | Chainsaw recall | Background threat FP |
| --- | ---: | ---: |
| Raw argmax | 0.976 (40/41) | 0.500 (36/72) |
| Validation-calibrated thresholds | 0.195 (8/41) | 0.000 (0/72) |

Calibration used validation-only threshold selection with `max_background_fp_rate=0.10` and `chainsaw` minimum recall target `0.45`. The validation constraint was not met: validation thresholded chainsaw recall was 0.320 with background threat FP 0.024.

Finding: forest_v1b contains a real chainsaw-like signal, but it does not learn a deployable cross-site decision boundary. On tambopata, the raw model finds most chainsaws only by also predicting half of held-out background as chainsaw. The calibrated operating point controls background false positives by suppressing most chainsaw detections. This fails the acoustic pass gate and should not re-enter fusion scoring.

Decision: do not start v1c, do not mine hard negatives from v1b, and do not tune architecture or thresholds around this result. The next useful data is deployment-site field audio: matched chainsaw positives and forest-at-rest background from the same microphones, sites, seasons, weather, and recording setup used by Canopy deployments. The operational collection specification is [Field Audio Data Requirements](../../docs/field-data-requirements.md). The pass gate remains chainsaw recall above 0.70 and background FP below 0.10 on a held-out set containing clips from at least 3 different RFCx or deployment sites.

Estimated timeline once minimum viable field data is received:

- Days 1-2: ingest audio, validate metadata, reject unusable rows, and produce a data quality report.
- Days 3-5: build an organization-scoped chainsaw/background manifest with complete-site held-out validation.
- Days 6-7: train and calibrate a field baseline, then report held-out recall and background false-positive rate.
- Week 2: if the fixed pass gate is met, run a limited org-only fusion pilot; if it is not met, keep acoustic confidence suppressed and return a concrete data gap report.
