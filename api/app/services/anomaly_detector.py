"""Open-set acoustic anomaly detection for the alert path.

This is the primary acoustic signal: instead of forcing every clip into a fixed
set of threat classes, we score how far a sound deviates from "normal forest
background" and, when anomalous, report a likelihood of what it seems to be
(including an honest ``unknown``).

When ``ANOMALY_MODEL_PATH`` is configured it loads the fitted detector from
``research.audio.anomaly_infer``; otherwise a deterministic filename fallback
keeps the dashboard and tests working with no torch/audio stack installed.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import get_settings

KNOWN_KINDS = ("chainsaw", "gunshot", "vehicle", "fire_crackle")
UNKNOWN_KIND = "unknown"


class AnomalyResult(BaseModel):
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool
    predicted_kind: str
    predicted_confidence: float = Field(..., ge=0.0, le=1.0)
    likelihoods: dict[str, float]
    model_version: str = "anomaly-fallback-v0"


def detect_anomaly(file_path: Path) -> AnomalyResult:
    settings = get_settings()
    if settings.anomaly_model_path:
        return _detect_with_model(file_path, Path(settings.anomaly_model_path))
    return _detect_with_filename_fallback(file_path)


def _detect_with_model(file_path: Path, model_dir: Path) -> AnomalyResult:
    detector = _detector(str(model_dir))
    result = detector.score(file_path)
    return AnomalyResult(
        anomaly_score=result["anomaly_score"],
        is_anomaly=result["is_anomaly"],
        predicted_kind=result["predicted_kind"],
        predicted_confidence=result["predicted_confidence"],
        likelihoods=result["likelihoods"],
        model_version=result.get("model_version", "anomaly-v1"),
    )


@lru_cache(maxsize=2)
def _detector(model_dir: str):
    try:
        from research.audio.anomaly_infer import AnomalyDetector
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "ANOMALY_MODEL_PATH is configured, but audio ML dependencies are not available. "
            "Install research/audio/requirements-audio.txt in the API environment."
        ) from exc
    return AnomalyDetector(Path(model_dir))


def _detect_with_filename_fallback(file_path: Path) -> AnomalyResult:
    """Deterministic demo fallback used only when no fitted detector is configured."""
    name = file_path.name.lower()
    if "chainsaw" in name or "saw" in name:
        return _result(0.93, {"chainsaw": 0.82, "vehicle": 0.06, UNKNOWN_KIND: 0.12})
    if "gunshot" in name or "shot" in name:
        return _result(0.90, {"gunshot": 0.61, "fire_crackle": 0.10, UNKNOWN_KIND: 0.29})
    if "vehicle" in name or "engine" in name or "truck" in name or "motor" in name:
        return _result(0.64, {"vehicle": 0.55, "chainsaw": 0.10, UNKNOWN_KIND: 0.35})
    if "anomaly" in name or "unknown" in name:
        return _result(0.78, {UNKNOWN_KIND: 1.0})
    return _result(0.18, {UNKNOWN_KIND: 1.0}, is_anomaly=False)


def _result(anomaly_score: float, likelihoods: dict[str, float], *, is_anomaly: bool = True) -> AnomalyResult:
    predicted_kind = max(likelihoods, key=likelihoods.get)
    return AnomalyResult(
        anomaly_score=anomaly_score,
        is_anomaly=is_anomaly,
        predicted_kind=predicted_kind,
        predicted_confidence=likelihoods[predicted_kind],
        likelihoods=likelihoods,
    )
