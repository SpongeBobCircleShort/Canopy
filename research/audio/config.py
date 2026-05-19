from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from research.audio.labels import LABELS

DEFAULT_CONFIG: dict[str, Any] = {
    "model_version": "threat-cnn-v2",
    "labels": LABELS,
    "audio": {
        "sample_rate": 16000,
        "clip_seconds": 4.0,
        "n_mels": 64,
    },
    "training": {
        "batch_size": 16,
        "epochs": 12,
        "learning_rate": 0.001,
        "seed": 42,
        "device": "auto",
        "class_weighting": False,
        "weighted_sampler": True,
        "sampler_weight_power": 0.75,
        "sampler_label_multipliers": {
            "chainsaw": 24.0,
            "gunshot": 2.0,
            "vehicle": 1.0,
            "fire_crackle": 16.0,
            "background_unknown": 1.5,
        },
        "checkpoint_each_epoch": True,
    },
    "evaluation": {
        "threshold_step": 0.05,
        "min_precision": {
            "chainsaw": 0.55,
            "gunshot": 0.8,
            "vehicle": 0.75,
            "fire_crackle": 0.6,
            "background_unknown": 0.8,
        },
        "selection": {
            "background_false_positive_penalty": 0.75,
            "min_recall": {
                "chainsaw": 0.6,
                "gunshot": 0.8,
                "vehicle": 0.7,
            },
        },
    },
    "augmentation": {
        "enabled": True,
        "gain_min": 0.85,
        "gain_max": 1.15,
        "noise_std": 0.003,
        "max_shift_fraction": 0.08,
        "max_time_mask_frames": 12,
        "max_freq_mask_bins": 8,
    },
    "paths": {
        "manifest": "data/audio/manifests/threat_manifest_v1.csv",
        "artifact_dir": "models/audio/threat_cnn_v2",
    },
}


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if path is None:
        path = Path(__file__).with_name("config.yaml")
    config_path = Path(path)
    if not config_path.exists():
        return config

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to read YAML config files") from exc

    loaded = yaml.safe_load(config_path.read_text()) or {}
    _deep_update(config, loaded)
    return config


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
