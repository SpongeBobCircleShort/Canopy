from pathlib import Path
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str = "placeholder-v0"


def classify_clip(file_path: Path) -> ClassificationResult:
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
