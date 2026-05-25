from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.audio.audio_io import load_log_mel, load_waveform_feature
from research.audio.config import load_config
from research.audio.labels import LABELS
from research.audio.model import build_model, model_config_from_checkpoint


def infer(model_dir: Path, audio_path: Path) -> dict:
    torch = _torch()
    config = load_config(model_dir / "config.yaml")
    checkpoint = torch.load(model_dir / "model.pt", map_location="cpu", weights_only=False)
    labels = json.loads((model_dir / "labels.json").read_text()) if (model_dir / "labels.json").exists() else LABELS

    model = build_model(len(labels), model_config=model_config_from_checkpoint(checkpoint, config.get("model", {})))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    if _feature_type(config.get("model", {})) == "waveform":
        features = load_waveform_feature(
            audio_path,
            sample_rate=int(config["audio"]["sample_rate"]),
            clip_seconds=float(config["audio"]["clip_seconds"]),
        ).unsqueeze(0)
    else:
        features = load_log_mel(
            audio_path,
            sample_rate=int(config["audio"]["sample_rate"]),
            clip_seconds=float(config["audio"]["clip_seconds"]),
            n_mels=int(config["audio"]["n_mels"]),
        ).unsqueeze(0)
    with torch.no_grad():
        probabilities = torch.softmax(model(features), dim=1)[0]
    score_map = {label: float(probabilities[index].item()) for index, label in enumerate(labels)}
    label = max(score_map, key=score_map.get)
    return {
        "label": label,
        "confidence": score_map[label],
        "model_version": checkpoint.get("artifact", {}).get("model_version", config.get("model_version", "threat-cnn-v0")),
        "scores": score_map,
    }


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to run audio inference") from exc
    return torch


def _feature_type(model_config: dict) -> str:
    if str(model_config.get("input", "")).lower() == "waveform":
        return "waveform"
    architecture = str(model_config.get("architecture", "cnn")).lower()
    if architecture in {"wav2vec2_frozen", "wav2vec2"}:
        return "waveform"
    return "log_mel"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline inference with a Canopy acoustic threat model.")
    parser.add_argument("--model", type=Path, required=True, help="Model artifact directory containing model.pt")
    parser.add_argument("--audio", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(infer(args.model, args.audio), indent=2))


if __name__ == "__main__":
    main()
