# Canopy Audio Threat Research

This directory contains the Phase 3A research prototype for a custom acoustic threat classifier. It is intentionally separate from the FastAPI runtime: `/api/clips/upload` still uses the existing placeholder classifier until a later integration step.

## Labels

The first model targets five operational classes:

- `chainsaw`
- `gunshot`
- `vehicle`
- `fire_crackle`
- `background_unknown`

## Setup

```bash
python3 -m venv .venv-audio
source .venv-audio/bin/activate
pip install -r research/audio/requirements-audio.txt
```

Training is intended for local macOS arm64 CPU/MPS or a separate GPU machine. The normal API and frontend dependencies do not install these ML packages.

## Build a Manifest

Audio data must stay outside git. Put public datasets under a local path such as `data/audio/raw/` or pass explicit dataset roots:

```bash
python -m research.audio.prepare_manifest \
  --esc50-root data/audio/raw/ESC-50 \
  --urbansound8k-root data/audio/raw/UrbanSound8K \
  --canopy-root data/audio/raw/canopy-labeled \
  --output data/audio/manifests/threat_manifest.csv
```

Manifest columns are:

```text
path,label,source,split,duration_seconds,license,notes
```

Supported sources are free text, with current builders emitting `esc50`, `urbansound8k`, and `canopy`.

## Train

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v1.csv \
  --config research/audio/config.yaml \
  --artifact-dir models/audio/threat_cnn_v2
```

Training uses a weighted sampler by default so scarce classes are not drowned out by vehicle/background examples. The default uses label-specific multipliers so `chainsaw` and `fire_crackle` get support without forcing every class to appear equally often. Training prints one JSON progress object per epoch with raw metrics, thresholded macro F1, background threat false-positive rate, and per-class recall, then writes the best false-positive-aware validation checkpoint to `model.pt`.

Artifacts:

- `model.pt`
- `best_model.pt`
- `labels.json`
- `val_metrics.json`
- `test_metrics.json`
- `history.json`
- `metrics.json`
- `checkpoint_epoch_*.pt`
- `config.yaml`

## Evaluate

```bash
python -m research.audio.evaluate \
  --model models/audio/threat_cnn_v2 \
  --manifest data/audio/manifests/threat_manifest_v1.csv \
  --split test
```

Evaluation writes `<split>_metrics.json` and includes raw macro F1, thresholded metrics, per-class recall, confusion matrices, background false-positive summaries, and per-class threshold recommendations. The v2 defaults choose thresholds with precision floors for threat labels and select checkpoints with a penalty for background clips predicted as threats.

## Offline Inference

```bash
python -m research.audio.infer \
  --model models/audio/threat_cnn_v2 \
  --audio /path/to/audio.wav
```

The CLI prints JSON compatible with the future Canopy classifier service boundary:

```json
{
  "label": "chainsaw",
  "confidence": 0.91,
  "model_version": "threat-cnn-v2",
  "scores": {
    "chainsaw": 0.91,
    "gunshot": 0.02,
    "vehicle": 0.04,
    "fire_crackle": 0.01,
    "background_unknown": 0.02
  }
}
```
