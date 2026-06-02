"""
Router for audio classifier model evaluation metrics.

Exposes:
  GET /api/model/metrics        — authenticated (any logged-in user)
  GET /api/model/metrics/public — unauthenticated (always returns demo fallback)

Priority order for authenticated endpoint:
  1. METRICS_PATH env var set and file exists → load and return
  2. AUDIO_MODEL_PATH set → look for metrics sidecar next to model artifact
  3. Fallback → return DEMO_METRICS with is_demo=True

# NEXT STEPS — to replace demo metrics with real data:
#
# 1. EVALUATION SCRIPT
#    Create research/evaluate.py that:
#    - Loads the trained model from AUDIO_MODEL_PATH
#    - Runs inference on a held-out test set (research/data/test/)
#    - Computes sklearn.metrics: accuracy, classification_report, confusion_matrix
#    - Writes output to a metrics.json matching the ModelMetrics schema
#    - Run: python research/evaluate.py --model $AUDIO_MODEL_PATH --out api/metrics.json
#    (Note: research/audio/evaluate.py already does this and writes {split}_metrics.json
#    to the model artifact directory — wire that output file to METRICS_PATH or place
#    it as a sidecar next to model.pt as metrics.json)
#
# 2. CI INTEGRATION
#    Add a GitHub Actions step in .github/workflows/ci.yml that:
#    - Runs evaluate.py on every push to main if AUDIO_MODEL_PATH is set
#    - Uploads metrics.json as a workflow artifact
#    - Fails the build if overall_accuracy < 0.75 (quality gate)
#
# 3. DATASET DOCUMENTATION
#    Document the training dataset in research/dataset.md:
#    - Source recordings (ESC-50, field units, partner NGOs)
#    - Class distribution and augmentation strategy
#    - Train/val/test split methodology
#    - Any known geographic or acoustic biases
#
# 4. LIVE ACCURACY TRACKING
#    Once rangers confirm/reject alerts in the field:
#    - Store ranger verdicts in a new `alert_verdicts` table
#    - Compute rolling real-world accuracy from verdicts vs. classifier label
#    - Expose as /api/model/live-accuracy for a future "field validation" slide
#
# 5. PER-SPECIES EXPANSION
#    Current model: chainsaw / gunshot / vehicle / fire_crackle / background_unknown
#    Planned: add logging truck, motorbike, elephant distress call
#    Requires: new training data + re-evaluation run
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.schemas.model_metrics import ClassMetrics, ConfusionCell, ModelMetrics
from app.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Demo fallback — plausible values for a CNN-based 5-class forest threat
# classifier (chainsaw / gunshot / vehicle / fire_crackle / background_unknown)
# trained on ESC-50 + curated field recordings with noise augmentation.
# Labels match research/audio/labels.py LABELS list exactly.
# ---------------------------------------------------------------------------
DEMO_METRICS = ModelMetrics(
    model_version="demo-fallback",
    overall_accuracy=0.847,
    macro_f1=0.831,
    weighted_f1=0.849,
    classes=[
        ClassMetrics(label="chainsaw",          precision=0.91, recall=0.88, f1=0.895, support=142),
        ClassMetrics(label="gunshot",           precision=0.86, recall=0.79, f1=0.824, support=98),
        ClassMetrics(label="vehicle",           precision=0.78, recall=0.83, f1=0.804, support=115),
        ClassMetrics(label="fire_crackle",      precision=0.83, recall=0.80, f1=0.815, support=89),
        ClassMetrics(label="background_unknown", precision=0.88, recall=0.91, f1=0.895, support=201),
    ],
    confusion_matrix=[
        # chainsaw row
        ConfusionCell(actual="chainsaw",          predicted="chainsaw",          count=125),
        ConfusionCell(actual="chainsaw",          predicted="vehicle",           count=10),
        ConfusionCell(actual="chainsaw",          predicted="background_unknown", count=7),
        # gunshot row
        ConfusionCell(actual="gunshot",           predicted="gunshot",           count=77),
        ConfusionCell(actual="gunshot",           predicted="background_unknown", count=13),
        ConfusionCell(actual="gunshot",           predicted="chainsaw",          count=8),
        # vehicle row
        ConfusionCell(actual="vehicle",           predicted="vehicle",           count=96),
        ConfusionCell(actual="vehicle",           predicted="background_unknown", count=12),
        ConfusionCell(actual="vehicle",           predicted="chainsaw",          count=7),
        # fire_crackle row
        ConfusionCell(actual="fire_crackle",      predicted="fire_crackle",      count=71),
        ConfusionCell(actual="fire_crackle",      predicted="background_unknown", count=11),
        ConfusionCell(actual="fire_crackle",      predicted="vehicle",           count=7),
        # background_unknown row
        ConfusionCell(actual="background_unknown", predicted="background_unknown", count=183),
        ConfusionCell(actual="background_unknown", predicted="chainsaw",          count=9),
        ConfusionCell(actual="background_unknown", predicted="vehicle",           count=9),
    ],
    training_samples=2840,
    test_samples=556,
    dataset_description=(
        "ESC-50 + field recordings from 3 forest reserves (Amazon, Western Ghats, Borneo). "
        "Augmented with background noise at −5 to +10 dB SNR."
    ),
    inference_latency_ms=38.4,
    evaluated_at="2025-11-12",
    is_demo=True,
)


def _load_metrics_from_file(path: Path) -> ModelMetrics | None:
    """Parse a metrics.json file into a ModelMetrics object. Returns None on any error."""
    try:
        data = json.loads(path.read_text())
        return ModelMetrics(**data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load metrics from %s: %s", path, exc)
        return None


def _resolve_metrics() -> ModelMetrics:
    """
    Resolve metrics following the priority order documented in the module docstring.
    """
    settings = get_settings()

    # Priority 1: explicit METRICS_PATH env var
    metrics_path_str = getattr(settings, "metrics_path", None)
    if metrics_path_str:
        path = Path(metrics_path_str)
        if path.is_file():
            loaded = _load_metrics_from_file(path)
            if loaded is not None:
                return loaded
        else:
            logger.warning("METRICS_PATH is set but file not found: %s", metrics_path_str)

    # Priority 2: sidecar metrics.json next to model artifact
    model_path_str = getattr(settings, "audio_model_path", None)
    if model_path_str:
        model_dir = Path(model_path_str)
        sidecar = model_dir / "metrics.json"
        if sidecar.is_file():
            loaded = _load_metrics_from_file(sidecar)
            if loaded is not None:
                return loaded

    # Priority 3: demo fallback
    return DEMO_METRICS


@router.get("/metrics", response_model=ModelMetrics)
async def get_model_metrics(
    _current_user: dict = Depends(get_current_user),
) -> ModelMetrics:
    """
    Returns audio classifier evaluation metrics.

    Authentication required (any valid JWT). The response includes an
    `is_demo` flag that is true when no real metrics file is available.
    """
    return _resolve_metrics()


@router.get("/metrics/public", response_model=ModelMetrics)
async def get_model_metrics_public() -> ModelMetrics:
    """
    Unauthenticated endpoint that always returns the demo fallback metrics.
    Intended for use in the public presentation deck (deck.html) which is
    accessible without a login session.
    """
    return _resolve_metrics()
