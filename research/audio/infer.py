from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.audio.audio_io import load_log_mel, load_waveform_feature
from research.audio.config import load_config
from research.audio.labels import LABELS
from research.audio.model import build_model, model_config_from_checkpoint


def infer(model_dir: Path, audio_path: Path) -> dict:
    return AudioInferenceService(model_dir).predict(audio_path)


class AudioInferenceService:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.torch = _torch()
        self.config = load_config(self.model_dir / "config.yaml")
        self.checkpoint = self.torch.load(self.model_dir / "model.pt", map_location="cpu", weights_only=False)
        self.labels = (
            json.loads((self.model_dir / "labels.json").read_text())
            if (self.model_dir / "labels.json").exists()
            else self.checkpoint.get("artifact", {}).get("labels", LABELS)
        )
        self.model_config = model_config_from_checkpoint(self.checkpoint, self.config.get("model", {}))
        self.model = build_model(len(self.labels), model_config=self.model_config)
        self.model.load_state_dict(self.checkpoint["state_dict"])
        self.model.eval()
        self.thresholds = _load_thresholds(self.model_dir)
        self.background_label = "background_unknown" if "background_unknown" in self.labels else self.labels[-1]

    def predict(self, audio_path: Path) -> dict:
        features = self._features(audio_path)
        with self.torch.no_grad():
            probabilities = self.torch.softmax(self.model(features), dim=1)[0]
        score_map = {label: float(probabilities[index].item()) for index, label in enumerate(self.labels)}
        label = _thresholded_label(score_map, self.thresholds, default_label=self.background_label)
        raw_label = max(score_map, key=score_map.get)
        return {
            "label": label,
            "confidence": score_map[label],
            "model_version": self.checkpoint.get("artifact", {}).get(
                "model_version", self.config.get("model_version", "threat-cnn-v0")
            ),
            "scores": score_map,
            "raw_label": raw_label,
        }

    def embed(self, audio_path: Path):
        """Return the model's pre-classifier embedding for a clip as a numpy array.

        v1 supports the CNN architecture (the deployed threat model): its
        ``features`` block ends in an AdaptiveAvgPool2d, so the flattened output
        is a fixed-length embedding regardless of clip length.
        """
        architecture = str(self.model_config.get("architecture", "cnn")).lower()
        if architecture not in {"cnn", "threat_cnn"} or not hasattr(self.model, "features"):
            raise ValueError(
                f"Anomaly embedding v1 supports the CNN architecture only; got '{architecture}'. "
                "Re-fit the anomaly detector with a CNN embedder model."
            )
        features = self._features(audio_path)
        with self.torch.no_grad():
            embedding = self.model.features(features).flatten(1)[0]
        return embedding.cpu().numpy()

    def _features(self, audio_path: Path):
        if _feature_type(self.model_config) == "waveform":
            return load_waveform_feature(
                audio_path,
                sample_rate=int(self.config["audio"]["sample_rate"]),
                clip_seconds=float(self.config["audio"]["clip_seconds"]),
            ).unsqueeze(0)
        return load_log_mel(
            audio_path,
            sample_rate=int(self.config["audio"]["sample_rate"]),
            clip_seconds=float(self.config["audio"]["clip_seconds"]),
            n_mels=int(self.config["audio"]["n_mels"]),
        ).unsqueeze(0)


def _load_thresholds(model_dir: Path) -> dict[str, float]:
    deployment_thresholds = _load_deployment_thresholds(model_dir / "deployment_thresholds.json")
    if deployment_thresholds:
        return deployment_thresholds
    metrics_path = model_dir / "val_metrics.json"
    if not metrics_path.exists():
        metrics_path = model_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        metrics = json.loads(metrics_path.read_text())
    except json.JSONDecodeError:
        return {}
    if "validation" in metrics:
        metrics = metrics["validation"]
    recommendations = metrics.get("threshold_recommendations", {})
    thresholds = {}
    for label, recommendation in recommendations.items():
        if isinstance(recommendation, dict):
            value = recommendation.get("threshold")
        else:
            value = recommendation
        try:
            thresholds[label] = float(value)
        except (TypeError, ValueError):
            continue
    return thresholds


def _load_deployment_thresholds(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    try:
        artifact = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    raw_thresholds = artifact.get("thresholds", artifact) if isinstance(artifact, dict) else {}
    thresholds = {}
    for label, value in raw_thresholds.items():
        try:
            thresholds[label] = float(value)
        except (TypeError, ValueError):
            continue
    return thresholds


def _thresholded_label(score_map: dict[str, float], thresholds: dict[str, float], *, default_label: str) -> str:
    if not thresholds:
        return max(score_map, key=score_map.get)
    passing = [
        (label, score)
        for label, score in score_map.items()
        if score >= thresholds.get(label, 0.5)
    ]
    if passing:
        return max(passing, key=lambda item: item[1])[0]
    return default_label


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
