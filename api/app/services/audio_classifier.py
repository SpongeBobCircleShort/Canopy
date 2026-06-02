from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field

from app.config import get_settings


class ClassificationResult(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str = "placeholder-v0"
    model_domain: str | None = None
    scores: dict[str, float] | None = None


def classify_clip(file_path: Path) -> ClassificationResult:
    settings = get_settings()
    if settings.audio_model_path:
        return _classify_with_model(file_path, Path(settings.audio_model_path))
    return _classify_with_filename_fallback(file_path)


def _classify_with_model(file_path: Path, model_dir: Path) -> ClassificationResult:
    service = _model_service(str(model_dir))
    prediction = service.predict(file_path)
    return ClassificationResult(
        label=prediction["label"],
        confidence=prediction["confidence"],
        model_version=prediction["model_version"],
        model_domain=model_domain_for_version(prediction["model_version"]),
        scores=prediction.get("scores"),
    )


@lru_cache(maxsize=2)
def _model_service(model_dir: str):
    try:
        from research.audio.infer import AudioInferenceService
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "AUDIO_MODEL_PATH is configured, but audio ML dependencies are not available. "
            "Install research/audio/requirements-audio.txt in the API environment."
        ) from exc
    return AudioInferenceService(Path(model_dir))


def _classify_with_filename_fallback(file_path: Path) -> ClassificationResult:
    """Deterministic demo fallback used only when no trained model is configured."""
    filename = file_path.name.lower()
    if "chainsaw" in filename or "saw" in filename:
        return ClassificationResult(label="chainsaw", confidence=0.82)
    if "gunshot" in filename or "shot" in filename:
        return ClassificationResult(label="gunshot", confidence=0.78)
    return ClassificationResult(label="unknown", confidence=0.35)


def model_domain_for_version(model_version: str | None) -> str | None:
    normalized = (model_version or "").lower().replace("_", "-")
    if "forest-v1" in normalized:
        return "forest_v1"
    if "expanded-v5" in normalized or "expanded-v6" in normalized or "-v5" in normalized or "-v6" in normalized:
        return "urban_cnn"
    return None
