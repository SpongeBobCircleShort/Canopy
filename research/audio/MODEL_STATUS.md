# Canopy Audio Model Status

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

Decision: do not start v1c, do not mine hard negatives from v1b, and do not tune architecture or thresholds around this result. The next useful data is deployment-site field audio: matched chainsaw positives and forest-at-rest background from the same microphones, sites, seasons, weather, and recording setup used by Canopy deployments. The pass gate remains chainsaw recall above 0.70 and background FP below 0.10 on a held-out set containing clips from at least 3 different RFCx or deployment sites.
