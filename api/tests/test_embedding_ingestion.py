"""Unit tests for the foundation-model satellite ingestion scoring.

Pure / offline: no Earth Engine, no network, no DB. Synthetic per-cell
observations are injected via ``fetch_fn`` and persistence via a fake
``create_satellite_change_fn``.
"""
from types import SimpleNamespace

from app.schemas import EmbeddingIngestRequest, SatelliteChangeSource, SatelliteChangeType
from app.services import embedding_ingestion as ei


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_embedding_change_identical_and_orthogonal() -> None:
    assert ei.embedding_change([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == 0.0
    assert ei.embedding_change([1.0, 0.0], [0.0, 1.0]) == 1.0


def test_embedding_change_handles_missing_or_degenerate() -> None:
    assert ei.embedding_change(None, [1.0]) is None
    assert ei.embedding_change([1.0], [1.0, 2.0]) is None  # length mismatch
    assert ei.embedding_change([0.0, 0.0], [1.0, 0.0]) is None  # zero norm


def test_dw_transition_and_classification() -> None:
    transition = ei.dw_transition({"trees": 0.9}, {"trees": 0.1, "bare": 0.7, "shrub_and_scrub": 0.2})
    assert transition == ("bare", 0.7)
    assert ei.classify_change_type(transition) is SatelliteChangeType.canopy_loss
    assert ei.classify_change_type(("shrub_and_scrub", 0.6)) is SatelliteChangeType.vegetation_stress
    assert ei.classify_change_type(None) is SatelliteChangeType.unknown


def test_score_cell_strong_loss_scores_high() -> None:
    severity, confidence, change_type = ei.score_cell(
        residual=0.4, change_scale=0.5, trees_delta=-0.6, transition=("bare", 0.7), neighbor_loss=4
    )
    assert severity == 0.8
    assert confidence > 0.8
    assert change_type is SatelliteChangeType.canopy_loss


# ---------------------------------------------------------------------------
# run_embedding_ingest
# ---------------------------------------------------------------------------

def _fake_create():
    created = []

    def _create(_org_id, payload):
        created.append(payload)
        return SimpleNamespace(id=len(created))

    return _create, created


def _request(**overrides) -> EmbeddingIngestRequest:
    params = dict(bbox=[80.0, 22.0, 80.3, 22.3], baseline_year=2019, recent_year=2023, grid_resolution=3)
    params.update(overrides)
    return EmbeddingIngestRequest(**params)


def _forest(trees=0.9):
    return {"trees": trees, "bare": 0.05, "shrub_and_scrub": 0.05}


def test_run_flags_only_the_changed_forest_cell() -> None:
    """A single cell with strong embedding change + tree→bare transition is flagged
    canopy_loss; stable forest around it is not."""
    cells = []
    for row in range(3):
        for col in range(3):
            changed = (row, col) == (1, 1)
            cells.append({
                "row": row, "col": col,
                "embedding_baseline": [1.0, 0.0],
                "embedding_recent": [0.0, 1.0] if changed else [1.0, 0.0],
                "dw_baseline": _forest(),
                "dw_recent": {"trees": 0.1, "bare": 0.8, "shrub_and_scrub": 0.1} if changed else _forest(),
            })

    create_fn, created = _fake_create()
    resp = ei.run_embedding_ingest(_request(), org_id=1, create_satellite_change_fn=create_fn, fetch_fn=lambda _r: cells)

    assert resp.backend == "earth_engine"
    assert resp.created_change_count == 1
    payload = created[0]
    assert payload.source is SatelliteChangeSource.satellite_embedding
    assert payload.change_type is SatelliteChangeType.canopy_loss
    assert payload.severity_score > 0.5
    assert payload.metadata["dw_transition_class"] == "bare"
    assert payload.metadata["baseline_year"] == 2019
    assert payload.metadata["grid_cell"] == [1, 1]


def test_regional_common_mode_is_removed() -> None:
    """A uniform change across the whole AOI (weather/sensor drift) must not flag any
    cell, because the regional median is subtracted."""
    # cosine 0.7 → change 0.3 for every cell, identically.
    drift_recent = [0.7, 0.714142]
    cells = [
        {
            "row": row, "col": col,
            "embedding_baseline": [1.0, 0.0],
            "embedding_recent": drift_recent,
            "dw_baseline": _forest(),
            "dw_recent": _forest(),
        }
        for row in range(3)
        for col in range(3)
    ]
    create_fn, created = _fake_create()
    resp = ei.run_embedding_ingest(_request(), org_id=1, create_satellite_change_fn=create_fn, fetch_fn=lambda _r: cells)
    assert resp.created_change_count == 0
    assert created == []


def test_non_forest_baseline_is_skipped() -> None:
    """A cell that wasn't forest at baseline is gated out even with a big change."""
    cells = [{
        "row": 0, "col": 0,
        "embedding_baseline": [1.0, 0.0],
        "embedding_recent": [0.0, 1.0],
        "dw_baseline": {"trees": 0.1, "bare": 0.8},  # not forest
        "dw_recent": {"trees": 0.0, "bare": 0.95},
    }]
    create_fn, created = _fake_create()
    resp = ei.run_embedding_ingest(
        _request(grid_resolution=1), org_id=1, create_satellite_change_fn=create_fn, fetch_fn=lambda _r: cells
    )
    assert resp.created_change_count == 0


def test_stub_fallback_without_fetch_backend() -> None:
    create_fn, created = _fake_create()
    resp = ei.run_embedding_ingest(_request(), org_id=1, create_satellite_change_fn=create_fn, fetch_fn=None)
    assert resp.backend == "stub"
    assert resp.created_change_count == 0
    assert created == []
