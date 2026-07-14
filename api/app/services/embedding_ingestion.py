"""Foundation-model satellite change detection.

Replaces hand-rolled NDVI differencing with two complementary Google Earth
Engine sources:

  * **AlphaEarth / Satellite Embedding V1 Annual** — a 64-d unit-length
    embedding per 10 m pixel, one per calendar year. Year-over-year semantic
    change is ``1 - cosine(e_baseline, e_recent)``. Because the embedding already
    fuses Sentinel-1 radar + multitemporal optical, this is far more robust to
    clouds, phenology and illumination than an NDVI delta. This is the primary,
    robust change signal.
  * **Dynamic World** — near-real-time 10 m land cover (9 classes incl. Trees /
    Bare / Shrub). The Trees-probability drop and the dominant Trees→non-Trees
    transition give a fast, *interpretable* "what changed" + recency layer that
    covers AlphaEarth's annual latency. This is the attribution signal.

This module is the **single source of truth** for the per-cell scoring math
(``score_cell``); the research validation spike imports it so the numbers it
reports are exactly what production computes. Earth Engine itself is a
batch *data-acquisition* layer injected as ``fetch_fn`` — this module has no
hard dependency on ``earthengine-api`` and runs (returning a graceful empty
"stub" result) without credentials.

Reuses the grid/severity/neighbour-clustering scaffolding from
``sentinel_ingestion`` rather than reinventing it.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Callable

from app.schemas import (
    EmbeddingIngestRequest,
    EmbeddingIngestResponse,
    SatelliteChangeCreate,
    SatelliteChangeSource,
    SatelliteChangeType,
)
from app.services.sentinel_ingestion import _cell_centroid, _median

log = logging.getLogger(__name__)

# Dynamic World band names (https://dynamicworld.app). We track the trees class
# and the non-tree classes a cleared forest cell typically transitions into.
_DW_TREES = "trees"
_DW_LOSS_CLASSES = ("bare", "crops", "built", "shrub_and_scrub")

# fetch_fn returns one of these per grid cell. Embeddings/dw maps may be None
# where Earth Engine had no usable observation for that cell.
CellObservation = dict[str, Any]
FetchFn = Callable[[EmbeddingIngestRequest], list[CellObservation]]


# ---------------------------------------------------------------------------
# Pure scoring helpers (no Earth Engine, fully unit-testable)
# ---------------------------------------------------------------------------

def embedding_change(e0: list[float] | None, e1: list[float] | None) -> float | None:
    """Semantic change = 1 - cosine similarity, in [0, 2]. None if unusable."""
    if not e0 or not e1 or len(e0) != len(e1):
        return None
    dot = sum(a * b for a, b in zip(e0, e1))
    n0 = math.sqrt(sum(a * a for a in e0))
    n1 = math.sqrt(sum(b * b for b in e1))
    if n0 < 1e-9 or n1 < 1e-9:
        return None
    cosine = max(-1.0, min(1.0, dot / (n0 * n1)))
    return 1.0 - cosine


def dw_trees_delta(dw0: dict[str, float] | None, dw1: dict[str, float] | None) -> float | None:
    """Change in Dynamic World trees probability (negative = canopy loss)."""
    if not dw0 or not dw1 or _DW_TREES not in dw0 or _DW_TREES not in dw1:
        return None
    return dw1[_DW_TREES] - dw0[_DW_TREES]


def dw_transition(dw0: dict[str, float] | None, dw1: dict[str, float] | None) -> tuple[str, float] | None:
    """Return (destination_class, recent_probability) for the dominant
    non-tree class a cell shifted toward, or None when DW is unavailable."""
    if not dw0 or not dw1:
        return None
    best_class, best_prob = None, -1.0
    for cls in _DW_LOSS_CLASSES:
        prob = dw1.get(cls, 0.0)
        if prob > best_prob:
            best_class, best_prob = cls, prob
    if best_class is None:
        return None
    return best_class, best_prob


def classify_change_type(transition: tuple[str, float] | None) -> SatelliteChangeType:
    """Map a Dynamic World transition to a change type. Without DW corroboration
    the cause is unattributed (``unknown``) even though the embedding flagged it."""
    if transition is None:
        return SatelliteChangeType.unknown
    to_class, _ = transition
    if to_class in ("bare", "crops", "built"):
        return SatelliteChangeType.canopy_loss
    if to_class == "shrub_and_scrub":
        return SatelliteChangeType.vegetation_stress
    return SatelliteChangeType.unknown


def score_cell(
    *,
    residual: float,
    change_scale: float,
    trees_delta: float | None,
    transition: tuple[str, float] | None,
    neighbor_loss: int,
) -> tuple[float, float, SatelliteChangeType]:
    """Return (severity, confidence, change_type) for one flagged cell.

    severity   — common-mode-removed embedding change residual, scaled.
    confidence — embedding-anomaly strength, boosted by Dynamic World agreement
                 (trees actually dropped), the destination-class probability,
                 and spatial coherence with neighbouring loss cells.
    """
    severity = max(0.0, min(residual / change_scale, 1.0))

    # Dynamic World agreement: did trees actually fall, and how confidently does
    # DW place the cell in its destination class?
    agreement = 0.0 if trees_delta is None else max(0.0, min(-trees_delta / 0.5, 1.0))
    to_class_prob = transition[1] if transition else 0.0

    confidence = (
        0.40
        + 0.25 * severity                 # strength of the embedding anomaly
        + 0.20 * agreement                # DW confirms canopy loss
        + 0.10 * to_class_prob            # DW confidence in the destination class
        + 0.05 * (neighbor_loss / 8.0)    # spatial coherence
    )
    confidence = round(max(0.30, min(0.98, confidence)), 4)
    return round(severity, 4), confidence, classify_change_type(transition)


# ---------------------------------------------------------------------------
# Public ingestion entry-point
# ---------------------------------------------------------------------------

def run_embedding_ingest(
    request: EmbeddingIngestRequest,
    *,
    org_id: int,
    create_satellite_change_fn: Any,
    fetch_fn: FetchFn | None = None,
) -> EmbeddingIngestResponse:
    """Execute a foundation-model satellite ingestion run.

    Args:
        request: validated ``EmbeddingIngestRequest``.
        org_id: organisation scoping key.
        create_satellite_change_fn: callable matching
            ``repositories.create_satellite_change`` (injected to avoid the DB
            import cycle).
        fetch_fn: returns per-cell AlphaEarth embeddings + Dynamic World class
            probabilities. Injected by the Earth Engine batch script (and by
            tests with synthetic cells). When ``None`` the run degrades
            gracefully to an empty "stub" result so the API works without EE
            credentials.
    """
    grid_n = request.grid_resolution

    if fetch_fn is None:
        log.warning(
            "Embedding ingest requested without an Earth Engine fetch backend; "
            "returning empty stub result. Configure EE and run the batch script "
            "(research/satellite) for real detections."
        )
        return EmbeddingIngestResponse(
            created_change_count=0,
            created_satellite_change_ids=[],
            cells_fetched=0,
            grid_cells_evaluated=grid_n * grid_n,
            skipped_count=0,
            backend="stub",
        )

    cells = fetch_fn(request)
    log.info("Embedding ingest fetched %d cells for org=%d bbox=%s", len(cells), org_id, request.bbox)

    # Pass 1 — raw embedding change for forest-eligible cells + the regional
    # (common-mode) trend. Atmospheric/seasonal/sensor drift shifts the whole
    # AOI together; the regional median is the benign drift we subtract.
    changes: list[float] = []
    cell_state: dict[tuple[int, int], dict[str, Any]] = {}
    for cell in cells:
        row, col = cell["row"], cell["col"]
        change = embedding_change(cell.get("embedding_baseline"), cell.get("embedding_recent"))
        if change is None:
            continue
        dw0, dw1 = cell.get("dw_baseline"), cell.get("dw_recent")
        # Baseline-forest gate: when DW is present, only consider cells that were
        # actually forest. Without DW we cannot gate on tree cover, so we keep the
        # cell and rely on the embedding signal alone.
        if dw0 and dw0.get(_DW_TREES, 0.0) < request.forest_baseline_min:
            continue
        changes.append(change)
        cell_state[(row, col)] = {
            "change": change,
            "trees_delta": dw_trees_delta(dw0, dw1),
            "transition": dw_transition(dw0, dw1),
        }

    regional_median_change = _median(changes) if changes else 0.0

    flagged: set[tuple[int, int]] = {
        rc
        for rc, st in cell_state.items()
        if (st["change"] - regional_median_change) >= request.change_threshold
    }

    # Pass 2 — emit a satellite change per flagged cell.
    created_ids: list[int] = []
    skipped_count = 0
    for (row, col), st in cell_state.items():
        if (row, col) not in flagged:
            skipped_count += 1
            continue
        residual = st["change"] - regional_median_change
        neighbor_loss = sum(
            1
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            if (dr or dc) and (row + dr, col + dc) in flagged
        )
        severity, confidence, change_type = score_cell(
            residual=residual,
            change_scale=request.change_scale,
            trees_delta=st["trees_delta"],
            transition=st["transition"],
            neighbor_loss=neighbor_loss,
        )
        lat, lon = _cell_centroid(request.bbox, grid_n, row, col)
        transition = st["transition"]
        transition_label = (
            f"trees → {transition[0]} ({transition[1]:.0%})" if transition else "unattributed"
        )
        payload = SatelliteChangeCreate(
            region_id=request.region_id,
            source=SatelliteChangeSource.satellite_embedding,
            change_type=change_type,
            severity_score=severity,
            confidence=confidence,
            image_date=None,
            latitude=lat,
            longitude=lon,
            description=(
                f"AlphaEarth semantic change {st['change']:.3f} "
                f"(residual {residual:+.3f} vs region {regional_median_change:.3f}); "
                f"Dynamic World {transition_label}; "
                f"{request.baseline_year}→{request.recent_year}."
            ),
            metadata={
                "embedding_change": round(st["change"], 4),
                "embedding_change_residual": round(residual, 4),
                "regional_median_change": round(regional_median_change, 4),
                "change_threshold": request.change_threshold,
                "dw_trees_delta": (round(st["trees_delta"], 4) if st["trees_delta"] is not None else None),
                "dw_transition_class": transition[0] if transition else None,
                "dw_transition_prob": (round(transition[1], 4) if transition else None),
                "baseline_year": request.baseline_year,
                "recent_year": request.recent_year,
                "grid_cell": [row, col],
                "grid_resolution": grid_n,
                "discriminators": {
                    "neighbor_loss_count": neighbor_loss,
                    "baseline_was_forest": True,
                },
            },
        )
        change = create_satellite_change_fn(org_id, payload)
        created_ids.append(change.id)

    log.info(
        "Embedding ingest complete: %d created, %d skipped of %d cells",
        len(created_ids), skipped_count, len(cell_state),
    )
    return EmbeddingIngestResponse(
        created_change_count=len(created_ids),
        created_satellite_change_ids=created_ids,
        cells_fetched=len(cells),
        grid_cells_evaluated=grid_n * grid_n,
        skipped_count=skipped_count,
        backend="earth_engine",
    )
