# =============================================================================
# Audit findings (Step 1):
#
# research/audio/:
#   - evaluate.py: full sklearn evaluation pipeline — accuracy_score,
#     classification_report, confusion_matrix — writes {split}_metrics.json
#     to the model artifact directory. No metrics.json exists yet (no trained
#     artifact has been committed; forest_v1b was evaluated locally per
#     MODEL_STATUS.md).
#   - labels.py: 5 classes — chainsaw, gunshot, vehicle, fire_crackle,
#     background_unknown
#   - model.py / train.py: CNN / ResNet18 architectures; multiple config YAMLs
#     show an active multi-experiment training history
#   - MODEL_STATUS.md: documents the latest held-out eval (forest_v1b /
#     tambopata). Chainsaw recall 0.976 raw but 0.195 post-calibration —
#     not deployment-ready. No committed metrics.json output.
#   - No Jupyter notebooks found in research/
#
# api/app/services/audio_classifier.py:
#   - Loads AUDIO_MODEL_PATH via lru_cache; delegates to AudioInferenceService
#   - Falls back to filename-based heuristic when no model configured
#   - Per-prediction confidence stored only in the alert record — no
#     aggregated accuracy tracking anywhere in the API layer
#
# api/app/config.py:
#   - audio_model_path: str | None — the only model-related env var
#   - No METRICS_PATH, no model_version field
#
# .env.example:
#   - AUDIO_STORAGE_PATH=/data/audio — present
#   - AUDIO_MODEL_PATH — absent (not documented)
#   - METRICS_PATH — absent (new, added in Step 3)
#
# Clip upload handler (api/app/routers/clips.py):
#   - Calls classify_clip() → stores label + confidence in alert record
#   - No batch accuracy logging, no model version telemetry beyond
#     classifier_model_version in the alert row
# =============================================================================

from typing import Optional

from pydantic import BaseModel


class ClassMetrics(BaseModel):
    label: str
    precision: float
    recall: float
    f1: float
    support: int


class ConfusionCell(BaseModel):
    actual: str
    predicted: str
    count: int


class ModelMetrics(BaseModel):
    model_version: str
    overall_accuracy: float
    macro_f1: float
    weighted_f1: float
    classes: list[ClassMetrics]
    confusion_matrix: list[ConfusionCell]
    training_samples: int
    test_samples: int
    dataset_description: Optional[str] = None
    inference_latency_ms: Optional[float] = None
    evaluated_at: Optional[str] = None
    is_demo: bool = False
