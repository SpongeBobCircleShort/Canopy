from functools import lru_cache
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings


class ClassificationResult(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str = "placeholder-v0"


BACKGROUND_LABEL = "background_unknown"


def classify_clip(file_path: Path) -> ClassificationResult:
    settings = get_settings()
    backend = settings.audio_classifier_backend.lower()
    if backend == "placeholder":
        return _classify_with_placeholder(file_path)
    if backend == "local_model":
        return _get_local_model_classifier(settings.audio_model_dir).classify(file_path)
    raise RuntimeError(f"Unsupported AUDIO_CLASSIFIER_BACKEND={settings.audio_classifier_backend!r}")


def _classify_with_placeholder(file_path: Path) -> ClassificationResult:
    """Deterministic placeholder classifier for the MVP slice.

    This intentionally avoids ML dependencies. It gives future model work a stable
    service boundary while producing predictable output for tests and demos.
    """
    filename = file_path.name.lower()
    if "chainsaw" in filename or "saw" in filename:
        return ClassificationResult(label="chainsaw", confidence=0.82)
    if "gunshot" in filename or "shot" in filename:
        return ClassificationResult(label="gunshot", confidence=0.78)
    return ClassificationResult(label="unknown", confidence=0.35)


class LocalAudioModelClassifier:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.torch, self.load_log_mel, self.load_config, self.build_model = _audio_research_dependencies()
        self.config = self.load_config(model_dir / "config.yaml")
        checkpoint = self.torch.load(model_dir / "model.pt", map_location="cpu")
        self.labels = _load_labels(model_dir)
        self.model = self.build_model(len(self.labels))
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()
        self.thresholds = _load_thresholds(model_dir, self.labels)
        self.model_version = checkpoint.get("artifact", {}).get("model_version", self.config.get("model_version", "threat-cnn-v1"))

    def classify(self, file_path: Path) -> ClassificationResult:
        features = self.load_log_mel(
            file_path,
            sample_rate=int(self.config["audio"]["sample_rate"]),
            clip_seconds=float(self.config["audio"]["clip_seconds"]),
            n_mels=int(self.config["audio"]["n_mels"]),
        ).unsqueeze(0)
        with self.torch.no_grad():
            probabilities = self.torch.softmax(self.model(features), dim=1)[0]
        scores = {label: float(probabilities[index].item()) for index, label in enumerate(self.labels)}
        label, confidence = choose_thresholded_label(scores, self.thresholds)
        return ClassificationResult(label=label, confidence=confidence, model_version=self.model_version)


def choose_thresholded_label(scores: dict[str, float], thresholds: dict[str, float]) -> tuple[str, float]:
    passing = {label: score for label, score in scores.items() if score >= thresholds.get(label, 0.5)}
    if passing:
        label = max(passing, key=passing.get)
        return label, passing[label]
    return BACKGROUND_LABEL, max(scores.values()) if scores else 0.0


@lru_cache(maxsize=4)
def _get_local_model_classifier(model_dir: str) -> LocalAudioModelClassifier:
    path = Path(model_dir)
    if not path.is_absolute():
        path = _repo_root() / path
    return LocalAudioModelClassifier(path)


def _load_labels(model_dir: Path) -> list[str]:
    labels_path = model_dir / "labels.json"
    if labels_path.exists():
        return json.loads(labels_path.read_text())
    return ["chainsaw", "gunshot", "vehicle", "fire_crackle", BACKGROUND_LABEL]


def _load_thresholds(model_dir: Path, labels: list[str]) -> dict[str, float]:
    for metrics_name in ("test_metrics.json", "metrics.json"):
        metrics_path = model_dir / metrics_name
        if not metrics_path.exists():
            continue
        data = json.loads(metrics_path.read_text())
        if "test" in data:
            data = data["test"]
        thresholds = data.get("threshold_recommendations", {})
        if thresholds:
            return {label: _threshold_value(thresholds.get(label), default=0.5) for label in labels}
    return {label: 0.5 for label in labels}


def _threshold_value(value: Any, *, default: float) -> float:
    if isinstance(value, dict):
        value = value.get("threshold", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _audio_research_dependencies():
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        import torch
        from research.audio.audio_io import load_log_mel
        from research.audio.config import load_config
        from research.audio.model import build_model
    except ImportError as exc:
        raise RuntimeError(
            "AUDIO_CLASSIFIER_BACKEND=local_model requires installing research/audio/requirements-audio.txt"
        ) from exc
    return torch, load_log_mel, load_config, build_model


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
