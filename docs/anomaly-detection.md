# Open-Set Acoustic Anomaly Detection

Canopy's acoustic path is a **catch-all anomaly detector**, not a fixed closed-set
classifier. Instead of forcing every sound into a small list of known threats, it
answers two questions:

1. **Is this sound anomalous?** How far does the clip deviate from *normal forest
   background*? → `anomaly_score ∈ [0, 1]`.
2. **What does the anomaly seem to be?** A likelihood over known threat kinds
   (`chainsaw`, `gunshot`, `vehicle`, `fire_crackle`) **plus an honest
   `unknown`** for sounds that match no known prototype.

## Why open-set

The previous closed-set CNN classifier overfit to its public/urban training
domain and failed site-held-out validation (`forest_v1b`: chainsaw recall
collapsed to 0.195 at a deployable false-positive rate — see
[research/audio/MODEL_STATUS.md](../research/audio/MODEL_STATUS.md)). It could
also only ever flag the four classes it was trained on.

The open-set design fixes both problems and, crucially, **ships on background-only
data**:

- The anomaly score is learned from *normal forest background alone*. No verified
  positives are required to start flagging unusual sounds.
- The "what is it" head uses per-class **prototypes** built from whatever verified
  positives exist. With zero positives, every anomaly is honestly `unknown` but
  still flagged. As verified positives arrive **per class**, that class lights up
  — no full retrain of the embedder.
- Background data directly controls the shared `background FP < 0.10` gate for
  every class at once.

## How it works (3 stages)

| Stage | What | Where |
| --- | --- | --- |
| Embedding | Reuse the CNN's 64-dim pre-classifier feature (`model.features → flatten`). Swappable for a pretrained encoder later. | [`infer.py`](../research/audio/infer.py) `AudioInferenceService.embed` |
| Anomaly score | Fit a shrunk-covariance Gaussian over background embeddings; score a clip by Mahalanobis distance, mapped to `[0,1]` via the empirical background CDF. The decision threshold sits at a background false-positive target. | [`anomaly.py`](../research/audio/anomaly.py) `fit_background`, `score_embedding` |
| Open-set likelihood | L2-normalized mean prototype per known class; cosine similarity → temperature-softmax with a reserved `unknown` mass when similarity is low. | [`anomaly.py`](../research/audio/anomaly.py) `fit_prototypes`, `_open_set_likelihoods` |

The numpy math in `anomaly.py` is intentionally torch-free so it is unit-tested
in CI without the audio stack ([`tests/test_anomaly.py`](../research/audio/tests/test_anomaly.py)).
The torch audio→embedding step lives in
[`anomaly_infer.py`](../research/audio/anomaly_infer.py).

## Fitting a detector from a background delivery

When the field background audio (e.g. the Indian forestry background delivery,
following [field-data-requirements.md](field-data-requirements.md)) lands, build a
manifest and fit:

```bash
python -m research.audio.fit_anomaly \
  --embedder-model models/audio/threat_cnn_kaggle_augmented_v1 \
  --background-manifest data/audio/manifests/india_background_v1.csv \
  --out models/audio/anomaly_v1
```

This writes `background_stats.npz`, `prototypes.npz` (empty until positives are
provided), and `detector_config.json`.

Add verified positives later — as few or as many classes as are available — to
light up the "what is it" likelihood:

```bash
python -m research.audio.fit_anomaly \
  --embedder-model models/audio/threat_cnn_kaggle_augmented_v1 \
  --background-manifest data/audio/manifests/india_background_v1.csv \
  --positives-manifest data/audio/manifests/india_positives_v1.csv \
  --out models/audio/anomaly_v1
```

The ranger-confirmation loop closes here: human labels added in the dashboard's
clip review are exported via `GET /api/clips/labels/export` and become the
positives manifest for the next re-fit — **no embedder retrain required**.

## Serving in the API

Set the artifact path and the clip-upload path uses the detector automatically:

```bash
export ANOMALY_MODEL_PATH=models/audio/anomaly_v1
```

`POST /api/clips/upload` then creates an `anomaly`-type alert. The score and
likelihoods are stored in the alert `metadata` (and returned in the upload
response):

```json
{
  "anomaly_score": 0.94,
  "is_anomaly": true,
  "predicted_kind": "chainsaw",
  "likelihoods": { "chainsaw": 0.71, "vehicle": 0.12, "unknown": 0.17 },
  "model_version": "anomaly-v1"
}
```

When `ANOMALY_MODEL_PATH` is unset, a deterministic filename fallback keeps the
dashboard and tests working with no torch/audio stack
([`anomaly_detector.py`](../api/app/services/anomaly_detector.py)).

Fusion treats `anomaly` alerts as the primary acoustic evidence (legacy `audio`
alerts are still honored), using `classifier_confidence` (the predicted-kind
confidence) as the acoustic signal.

## Dashboard

Anomaly alerts render an **anomaly score** plus a ranked likelihood breakdown
([`AnomalyLikelihood.jsx`](../frontend/src/components/AnomalyLikelihood.jsx)),
e.g. `likely chainsaw 71% · vehicle 12% · unknown 17%`. The alert-type filter
includes an **Anomaly** option.

## Current limitations and the promotion gate

- The embedding currently reuses the existing CNN, which carries some domain
  bias. The interface is built to swap in a pretrained audio encoder (PANNs /
  YAMNet) without changing the anomaly math.
- `anomaly_score` is **not** yet fed into fusion scoring; acoustic confidence
  stays suppressed until a model passes the field gate (chainsaw recall > 0.70
  and background FP < 0.10 on held-out clips from ≥ 3 sites).
- A populated "what is it" likelihood for a class requires verified field
  positives for that class; until then those anomalies read `unknown`.
