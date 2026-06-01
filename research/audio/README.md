# Canopy Audio Threat Research

This directory contains the Phase 3A research prototype for a custom acoustic threat classifier. The FastAPI runtime can use a trained artifact when `AUDIO_MODEL_PATH` points at a model directory containing `model.pt`, `config.yaml`, and `labels.json`. If that variable is unset, `/api/clips/upload` falls back to the deterministic filename classifier used by lightweight demos and tests.

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

Kaggle gunshot and vehicle datasets can be imported into standalone manifests and curation sheets:

```bash
python -m research.audio.import_kaggle_chainsaw \
  --dataset tuanhaanh/chainsaw-sound-in-a-raining-forest \
  --output data/audio/manifests/kaggle_chainsaw_manifest.csv \
  --curation-output data/audio/curation/kaggle_chainsaw_curation.csv

python -m research.audio.import_kaggle_gunshot \
  --output data/audio/manifests/kaggle_gunshot_manifest.csv \
  --curation-output data/audio/curation/kaggle_gunshot_curation.csv

python -m research.audio.import_kaggle_vehicle \
  --dataset janboubiabderrahim/vehicle-sounds-dataset \
  --output data/audio/manifests/kaggle_vehicle_manifest.csv \
  --curation-output data/audio/curation/kaggle_vehicle_curation.csv

python -m research.audio.import_kaggle_fire \
  --dataset forestprotection/forest-wild-fire-sound-dataset \
  --output data/audio/manifests/kaggle_forest_wildfire_manifest.csv \
  --curation-output data/audio/curation/kaggle_forest_wildfire_curation.csv
```

If a Kaggle download was already extracted, pass `--root /path/to/dataset`. Review the generated curation sheets before merging these rows into a training manifest. The vehicle importer groups sequential `VehicleNoise*` files by numeric blocks to reduce adjacent-clip train/validation/test leakage. The chainsaw importer defaults to `tuanhaanh/chainsaw-dataset-with-forest-ambiance` and treats all audio files in the dataset as weak-labelled `chainsaw` examples. The forest wildfire importer labels clips as `fire_crackle`.

### FSC22 forest negatives (train-only)

[FSC22](https://github.com/IRMIOT/FSC22) is a forest-specific benchmark (~2,025 clips, 27 classes, 5 s, CC0). By default the importer keeps **non-threat** classes as `background_unknown` or `vehicle` and skips threat classes (`Fire`, `Chainsaw`, `Gunshot`, etc.) so it can be merged as training negatives without polluting val/test.

Clone or extract the dataset under `data/audio/raw/FSC22` (expected layout: `Audios/*.wav` and `Metadata/Metadata V1.0 FSC22.csv`), then:

```bash
python -m research.audio.import_fsc22 \
  --download \
  --root data/audio/raw/FSC22 \
  --output data/audio/manifests/fsc22_negatives_manifest.csv \
  --curation-output data/audio/curation/fsc22_negatives_curation.csv
```

Optional flags:

- `--max-per-class 50` — cap each FSC22 class before merging (recommended when experimenting).
- `--include-threat-classes` — also import threat rows (mapped to Canopy labels); use only for train-only augmentation after review.
- `--balanced-splits` — assign train/val/test instead of the default train-only lock.

Negatives-only import yields about **1,500** rows (18 background classes + 2 vehicle classes × 75 clips). Merge into a training manifest after review; do not add unreviewed FSC22 rows to test.

### Kaggle-balanced manifest (train-only augmentation)

When the full Kaggle vehicle corpus would dominate training, build a capped manifest on top of `threat_manifest_expanded_hn_v4.csv`:

```bash
python -m research.audio.build_kaggle_balanced_manifest \
  --base-manifest data/audio/manifests/threat_manifest_expanded_hn_v4.csv \
  --kaggle-chainsaw-manifest data/audio/manifests/kaggle_chainsaw_manifest.csv \
  --kaggle-gunshot-manifest data/audio/manifests/kaggle_gunshot_manifest.csv \
  --kaggle-fire-manifest data/audio/manifests/kaggle_forest_wildfire_manifest.csv \
  --kaggle-vehicle-manifest data/audio/manifests/kaggle_vehicle_janboubiabderrahim_manifest.csv \
  --output data/audio/manifests/threat_manifest_kaggle_balanced_v2.csv \
  --chainsaw-target-rows 300 \
  --gunshot-target-rows 500 \
  --fire-target-rows 500 \
  --vehicle-target-rows 1400

python -m research.audio.report_manifest \
  --manifest data/audio/manifests/threat_manifest_kaggle_balanced_v2.csv \
  --output data/audio/manifests/threat_manifest_kaggle_balanced_v2_report.json \
  --min-test-support 100
```

The builder keeps all Kaggle rows on `train`, caps vehicle clips with round-robin sampling across vehicle folders, and leaves `val`/`test` on the v4 benchmark distribution. Default caps are 300 chainsaw, 500 gunshot, 500 fire (or all available wildfire clips if fewer), and 1400 vehicle.

Train and calibrate the balanced CNN:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_kaggle_balanced_v2.csv \
  --config research/audio/config_cnn_kaggle_balanced_v2.yaml \
  --artifact-dir models/audio/threat_cnn_kaggle_balanced_v2

python -m research.audio.calibrate_thresholds \
  --model models/audio/threat_cnn_kaggle_balanced_v2 \
  --manifest data/audio/manifests/threat_manifest_kaggle_balanced_v2.csv \
  --threshold-step 0.05 \
  --max-background-fp-rate 0.10 \
  --min-recall chainsaw=0.5 gunshot=0.65 vehicle=0.35 fire_crackle=0.45
```

If background threat false positives stay high after v2, try the background-conservative follow-up config on the same manifest:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_kaggle_balanced_v2.csv \
  --config research/audio/config_cnn_kaggle_balanced_v3_bg.yaml \
  --artifact-dir models/audio/threat_cnn_kaggle_balanced_v3_bg
```

#### Balanced v2 results (local CPU run, Jun 2026)

| Model | Test raw macro F1 | Test thresholded macro F1 | Test bg threat FP (thresholded) | Test gunshot recall (raw) |
| --- | ---: | ---: | ---: | ---: |
| `threat_cnn_expanded_hn_v3` | 0.596 | 0.474 | 0.139 | 0.900 |
| `threat_cnn_kaggle_augmented_v1` | 0.540 | 0.317 | 0.102 | 0.760 |
| `threat_cnn_kaggle_balanced_v2` | 0.323 | 0.444 | 0.250 | 0.840 |

After validation-only deployment calibration (`max-background-fp-rate 0.10`):

| Model | Deployment test macro F1 | Deployment test bg threat FP | Deployment test gunshot recall |
| --- | ---: | ---: | ---: |
| `threat_cnn_expanded_hn_v3` | 0.525 | 0.185 | 0.670 |
| `threat_cnn_kaggle_augmented_v1` | 0.516 | 0.194 | 0.610 |
| `threat_cnn_kaggle_balanced_v2` | 0.462 | 0.324 | 0.630 |

Balanced v2 beats the vehicle-dominated Kaggle-augmented model on thresholded macro F1 and preserves higher raw gunshot recall, but it still over-predicts `chainsaw` on background and vehicle clips. No threshold grid on the v2 test split reached a background threat false-positive rate at or below 0.10. For deployable safety, prefer `threat_cnn_expanded_hn_v3` until a v3-bg retrain or additional hard-negative mining reduces chainsaw false alarms.

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

To train the CNN with the Kaggle chainsaw rainforest and vehicle sounds rows layered on top of the expanded hard-negative manifest, use:

```bash
python -m research.audio.train \
  --manifest data/audio/manifests/threat_manifest_kaggle_augmented_v1.csv \
  --config research/audio/config_cnn_kaggle_augmented_v1.yaml \
  --artifact-dir models/audio/threat_cnn_kaggle_augmented_v1
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

## Calibrate Deployment Thresholds

Use validation-only calibration before promoting a trained artifact for runtime triage:

```bash
python -m research.audio.calibrate_thresholds \
  --model models/audio/threat_cnn_expanded_hn_v3 \
  --manifest data/audio/manifests/threat_manifest_expanded_hn_v3.csv \
  --threshold-step 0.05 \
  --max-background-fp-rate 0.15 \
  --min-recall chainsaw=0.55 gunshot=0.65 vehicle=0.40 fire_crackle=0.40
```

The calibrator writes `deployment_thresholds.json`, `calibration_metrics.json`, and `test_metrics_deployment_thresholds.json` into the model directory. It searches deployment thresholds on the validation split only, then evaluates the selected thresholds on test for reporting.

## Error Audit

Before retraining, export per-clip errors and listen through the highest-priority rows:

```bash
python -m research.audio.error_audit \
  --model models/audio/threat_cnn_expanded_hn_v3 \
  --manifest data/audio/manifests/threat_manifest_expanded_hn_v3.csv \
  --split val \
  --output data/audio/audits/threat_cnn_expanded_hn_v3_val_error_audit.csv
```

The audit CSV includes the clip path, source, split, true label, raw prediction, thresholded prediction, per-class scores, error type, and review priority. Priority `1` rows are background false positives, priority `2` rows are threats missed as background, and priority `3` rows are threat-to-threat confusions. The companion `*_top_confusions.json` summarizes the largest error buckets. Use validation and train audits for relabel/remove decisions; keep test locked except for documenting suspected label defects.

### Review App

Run the local review app from the repository root:

```bash
python -m research.audio.review_app
```

Open `http://127.0.0.1:8765/`. The app loads audit CSVs from `data/audio/audits/`, streams local audio files, filters by label/error/source/priority, and writes review decisions to `data/audio/curation/audio_review_decisions.csv`.

## Offline Inference

```bash
python -m research.audio.infer \
  --model models/audio/threat_cnn_expanded_hn_v3 \
  --audio /path/to/audio.wav
```

The CLI prints JSON compatible with the future Canopy classifier service boundary:

```json
{
  "label": "chainsaw",
  "confidence": 0.91,
  "model_version": "threat-cnn-expanded-hn-v3",
  "scores": {
    "chainsaw": 0.91,
    "gunshot": 0.02,
    "vehicle": 0.04,
    "fire_crackle": 0.01,
    "background_unknown": 0.02
  },
  "raw_label": "chainsaw"
}
```

Inference first loads `deployment_thresholds.json` when present, then falls back to `val_metrics.json` threshold recommendations. A class must pass its selected threshold to become the final label; otherwise the result defaults to `background_unknown`. This keeps deployment behavior aligned with the false-positive controls used during model selection and calibration.

## API Runtime Integration

Install the audio dependencies in the API runtime and point the service at a trained artifact:

```bash
export AUDIO_MODEL_PATH=models/audio/threat_cnn_expanded_hn_v3
```

The model is loaded lazily and cached by the classifier service. Leave `AUDIO_MODEL_PATH` unset for local API tests or demo flows that should avoid PyTorch and torchaudio.
