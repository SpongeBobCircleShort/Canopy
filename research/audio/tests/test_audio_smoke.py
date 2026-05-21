from __future__ import annotations

import json
import math
import wave
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchaudio")
pytest.importorskip("yaml")

from research.audio.audio_io import load_and_preprocess_audio, load_log_mel
from research.audio.infer import infer
from research.audio.labels import LABELS
from research.audio.manifest import ManifestRow, write_manifest
from research.audio.train import train


def test_audio_preprocessing_shape(tmp_path: Path) -> None:
    audio_path = tmp_path / "tone.wav"
    _write_tone(audio_path, frequency=440, sample_rate=4000, seconds=0.1)

    waveform = load_and_preprocess_audio(audio_path, sample_rate=8000, clip_seconds=0.25)
    features = load_log_mel(audio_path, sample_rate=8000, clip_seconds=0.25, n_mels=16)

    assert waveform.shape == (1, 2000)
    assert features.shape[0] == 1
    assert features.shape[1] == 16


def test_tiny_training_evaluation_and_inference_smoke(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    artifact_dir = tmp_path / "artifact"
    config_path = tmp_path / "config.yaml"
    rows = []
    frequencies = {
        "chainsaw": 220,
        "gunshot": 330,
        "vehicle": 440,
        "fire_crackle": 550,
        "background_unknown": 660,
    }
    for label, frequency in frequencies.items():
        for split_index, split in enumerate(["train", "val", "test"]):
            audio_path = tmp_path / f"{label}-{split}.wav"
            _write_tone(audio_path, frequency=frequency + split_index, sample_rate=8000, seconds=0.25)
            rows.append(ManifestRow(path=str(audio_path), label=label, source="synthetic", split=split, duration_seconds=0.25))
    write_manifest(manifest_path, rows)
    config_path.write_text(
        """
model_version: threat-cnn-smoke
labels:
  - chainsaw
  - gunshot
  - vehicle
  - fire_crackle
  - background_unknown
model:
  architecture: cnn
  dropout: 0.0
audio:
  sample_rate: 8000
  clip_seconds: 0.25
  n_mels: 16
training:
  batch_size: 5
  epochs: 1
  learning_rate: 0.001
  seed: 7
  device: cpu
  class_weighting: true
  weighted_sampler: true
  sampler_weight_power: 0.75
  sampler_label_multipliers:
    chainsaw: 2.0
    gunshot: 2.0
    vehicle: 1.0
    fire_crackle: 2.0
    background_unknown: 1.0
  checkpoint_each_epoch: true
  scheduler: none
loss:
  name: cross_entropy
evaluation:
  threshold_step: 0.05
  min_precision:
    chainsaw: 0.0
    gunshot: 0.0
    vehicle: 0.0
    fire_crackle: 0.0
    background_unknown: 0.0
  selection:
    background_false_positive_penalty: 0.5
    min_recall:
      chainsaw: 0.0
augmentation:
  enabled: false
paths:
  manifest: unused.csv
  artifact_dir: unused
""".strip()
    )

    metrics = train(manifest_path, config_path, artifact_dir)
    result = infer(artifact_dir, tmp_path / "chainsaw-test.wav")

    assert (artifact_dir / "model.pt").exists()
    assert (artifact_dir / "best_model.pt").exists()
    assert (artifact_dir / "labels.json").exists()
    assert (artifact_dir / "metrics.json").exists()
    assert (artifact_dir / "val_metrics.json").exists()
    assert (artifact_dir / "test_metrics.json").exists()
    assert (artifact_dir / "history.json").exists()
    assert (artifact_dir / "checkpoint_epoch_001.pt").exists()
    assert json.loads((artifact_dir / "labels.json").read_text()) == LABELS
    assert "macro_f1" in metrics
    assert "thresholded_metrics" in metrics
    assert "background_false_positive_summary" in metrics
    assert "selection_score" in metrics
    assert result["label"] in LABELS
    assert 0 <= result["confidence"] <= 1
    assert set(result["scores"]) == set(LABELS)


def _write_tone(path: Path, *, frequency: float, sample_rate: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(frames):
            sample = int(16000 * math.sin(2 * math.pi * frequency * index / sample_rate))
            handle.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))
