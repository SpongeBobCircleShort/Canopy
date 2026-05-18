from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from research.audio.labels import LABELS

DEFAULT_CONFIG: dict[str, Any] = {
    "model_version": "threat-cnn-v0",
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
    },
    "paths": {
        "manifest": "data/audio/manifests/threat_manifest.csv",
        "artifact_dir": "models/audio/threat_cnn_v0",
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
