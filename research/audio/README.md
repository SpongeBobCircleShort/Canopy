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
  --fsd50k-root data/audio/raw/FSD50K \
  --rfcx-frugalai-root data/audio/raw/RFCx-FrugalAI \
  --zenodo-gunshot-root data/audio/raw/Gunshot-Gunfire-Zenodo \
  --dcase2017-task2-root data/audio/raw/DCASE2017-task2 \
  --canopy-root data/audio/raw/canopy-labeled \
  --hard-negative-manifest data/audio/manifests/hard_negatives_v3.csv \
  --output data/audio/manifests/threat_manifest_v4.csv
```

Manifest columns are:

```text
path,label,source,split,duration_seconds,license,notes
```

Supported sources are free text, with current builders emitting `esc50`, `urbansound8k`, `fsd50k`, `rfcx_frugalai`, `zenodo_gunshot_gunfire`, `dcase2017_task2`, `canopy`, and `hard_negative`. Optional public datasets expect local audio plus metadata extracted under one root. Canopy-labeled folders can be nested, for example `data/audio/raw/canopy-labeled/background_unknown/hard_vehicle_like/*.wav`.

For scarce-class expansion without downloading the full multi-part FSD50K audio archive, download the official FSD50K metadata zips and then fetch only selected mirror files:

```bash
python -m research.audio.download_fsd50k_candidates \
  --fsd50k-root data/audio/raw/FSD50K \
  --existing-manifest data/audio/manifests/threat_manifest_v4.csv \
  --min-test-support 100
```

This selects FSD50K eval clips for `chainsaw`, `fire_crackle`, and `gunshot` until the manifest reaches the requested test support. It writes audio under `data/audio/raw/FSD50K/FSD50K.eval_audio/` and a local review sheet at `data/audio/curation/fsd50k_selected_candidates.csv`. These are weak-labeled public candidates, so review the sheet and listen before treating them as final verified test truth.

Use the same tool with `--hf-split dev --manifest-split val` to raise validation support:

```bash
python -m research.audio.download_fsd50k_candidates \
  --fsd50k-root data/audio/raw/FSD50K \
  --existing-manifest data/audio/manifests/threat_manifest_v4.csv \
  --min-test-support 100 \
  --hf-split dev \
  --manifest-split val \
  --curation-output data/audio/curation/fsd50k_val_candidates.csv
```

The downloader writes `data/audio/raw/FSD50K/FSD50K.selected_splits.csv`; the manifest builder uses that file to lock selected FSD50K `dev` clips to validation.

Additional labelled datasets can be layered in without changing training code:

- RFCx FrugalAI rainforest chainsaw/background clips. The dataset is gated on Hugging Face; accept the terms and set `HF_TOKEN` if required, then run:

  ```bash
  python -m research.audio.download_rfcx_frugalai \
    --output-root data/audio/raw/RFCx-FrugalAI \
    --max-chainsaw-per-split 250 \
    --max-background-per-split 250
  ```

- Gunshot/Gunfire Audio Dataset from Zenodo. Extract it locally under `data/audio/raw/Gunshot-Gunfire-Zenodo/`; the manifest builder treats audio files under this root as `gunshot`, preserving `train`/`val`/`test` or `testing` folder names when present.
- DCASE 2017 Task 2 rare sound events. Extract it under `data/audio/raw/DCASE2017-task2/`; the manifest builder reads event metadata CSVs and imports rows whose event label is `gunshot`.

Keep these datasets out of git. RFCx and DCASE are useful for diversity, but do not put weakly reviewed third-party clips into the final test set until you have listened to them and confirmed licensing for your intended use.

Manifest splitting is group-aware by default. Rows with the same `source_recording_id`, `recording_id`, `source_recording`, `source_file`, `site_id`, `video_id`, or `clip_id` note stay in the same split; known public dataset filenames are also grouped to reduce train/test contamination.

For manually verified scarce-class clips, use explicit split folders. These rows keep the requested split instead of being reshuffled:

```text
data/audio/raw/canopy-labeled/chainsaw/train/*.wav
data/audio/raw/canopy-labeled/chainsaw/val/*.wav
data/audio/raw/canopy-labeled/chainsaw/test/*.wav
data/audio/raw/canopy-labeled/fire_crackle/train/*.wav
data/audio/raw/canopy-labeled/fire_crackle/val/*.wav
data/audio/raw/canopy-labeled/fire_crackle/test/*.wav
data/audio/raw/canopy-labeled/gunshot/train/*.wav
data/audio/raw/canopy-labeled/gunshot/val/*.wav
data/audio/raw/canopy-labeled/gunshot/test/*.wav
```

The alternate layout `data/audio/raw/canopy-labeled/test/chainsaw/*.wav` is also supported.

Use this filename convention for curated clips:

```text
<label>__<source_recording_id>__<start_seconds>_<end_seconds>__<short_note>.wav
```

Example:

```text
chainsaw__yt-abc123__031.0_035.0__distant-idle.wav
```

The manifest builder parses `source_recording_id`, start/end seconds, and the note from filenames that follow this convention. Source recording IDs are used by reports to detect train/test contamination.

Create or validate a local curation sheet:

```bash
python -m research.audio.curation_sheet \
  --canopy-root data/audio/raw/canopy-labeled \
  --output data/audio/curation/canopy_audio_curation.csv

python -m research.audio.curation_sheet \
  --validate data/audio/curation/canopy_audio_curation.csv
```

The curation sheet columns are `path,label,split,source_recording_id,site_id,license,reviewer,decision,notes`. Mark accepted clips with `decision=accepted`; accepted rows must have a source recording ID.

## Mine Hard Negatives

```bash
python -m research.audio.mine_hard_negatives \
  --model models/audio/threat_cnn_v3 \
  --manifest data/audio/manifests/threat_manifest_v3.csv \
  --output data/audio/manifests/hard_negatives_v3.csv \
  --split train \
  --min-confidence 0.5
```

Hard negatives are background clips that the current model misclassifies as `chainsaw`, `gunshot`, or `vehicle`; when imported back into a manifest they are locked to the training split.

## Report Manifest Quality

```bash
python -m research.audio.report_manifest \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --output data/audio/manifests/threat_manifest_v4_report.json \
  --min-test-support 100
```

Use `--experimental` only for exploratory runs. Without it, the report fails when any target label has fewer than 100 test examples or when a source recording appears in multiple splits.

The report includes collection targets for scarce classes. `additional_verified_test_rows_needed` is the direct number of manually verified test clips needed; `estimated_additional_total_rows_needed_with_balanced_split` estimates how many total new clips are needed if relying on a 15% automatic test split.

## Train

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v3.csv \
  --config research/audio/config.yaml \
  --artifact-dir models/audio/threat_cnn_v3
```

Training uses a weighted sampler by default so scarce classes are not drowned out by vehicle/background examples. The active v3 config uses the CNN baseline with label-specific sampler multipliers and a source multiplier that oversamples imported `hard_negative` rows. Augmentation supports gain/noise/time shift and mild SpecAugment. Training prints one JSON progress object per epoch with raw metrics, thresholded macro F1, background threat false-positive rate, raw per-class recall, and thresholded per-class recall, then writes the best false-positive-aware validation checkpoint to `model.pt`.

To test whether the larger v4 manifest helps without the failed ResNet/focal-loss/background-mix changes, run the controlled CNN ablation:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --config research/audio/config_cnn_v4_ablation.yaml \
  --artifact-dir models/audio/threat_cnn_v4_ablation_cnn
```

This keeps the v3 CNN recipe, uses cross entropy, and adds threshold constraints for per-threat background false-positive rates.

To test a larger Mel-spectrogram image model without the failed v4 focal-loss/background-mix recipe, run the controlled ResNet18 ablation:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --config research/audio/config_resnet18_mel_v4_ablation.yaml \
  --artifact-dir models/audio/threat_resnet18_mel_v4_ablation
```

If the first ResNet run over-alerts on background, run the background-conservative variant:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --config research/audio/config_resnet18_mel_v4_bg_conservative.yaml \
  --artifact-dir models/audio/threat_resnet18_mel_v4_bg_conservative
```

If the conservative run controls background false positives but suppresses threat recall too much, run the recall-rebalance variant:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --config research/audio/config_resnet18_mel_v4_recall_rebalance.yaml \
  --artifact-dir models/audio/threat_resnet18_mel_v4_recall_rebalance
```

If recall-rebalance stays under the background false-positive target but chainsaw recall remains low, run the chainsaw-recall variant:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --config research/audio/config_resnet18_mel_v4_chainsaw_recall.yaml \
  --artifact-dir models/audio/threat_resnet18_mel_v4_chainsaw_recall
```

To train a pretrained-embedding baseline, use the frozen wav2vec2 encoder config:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_v4.csv \
  --config research/audio/config_wav2vec2_v4.yaml \
  --artifact-dir models/audio/threat_wav2vec2_v4
```

This feeds waveform audio into a frozen pretrained `torchaudio` wav2vec2 encoder and trains only a small classifier head. The first run may download the wav2vec2 bundle weights through `torchaudio`.

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
  --model models/audio/threat_cnn_v3 \
  --manifest data/audio/manifests/threat_manifest_v3.csv \
  --split test
```

Evaluation writes `<split>_metrics.json` and includes raw macro F1, thresholded metrics, per-class recall, confusion matrices, background false-positive summaries, and per-class threshold recommendations. The active v3 defaults choose thresholds with precision floors and select checkpoints with a penalty for background clips predicted as threats.

## Offline Inference

```bash
python -m research.audio.infer \
  --model models/audio/threat_cnn_v3 \
  --audio /path/to/audio.wav
```

The CLI prints JSON compatible with the future Canopy classifier service boundary:

```json
{
  "label": "chainsaw",
  "confidence": 0.91,
  "model_version": "threat-cnn-v3",
  "scores": {
    "chainsaw": 0.91,
    "gunshot": 0.02,
    "vehicle": 0.04,
    "fire_crackle": 0.01,
    "background_unknown": 0.02
  }
}
```
