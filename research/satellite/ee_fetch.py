"""Earth Engine fetch layer for the foundation-model satellite pipeline.

Pulls, per grid cell over a bbox:
  * the Google AlphaEarth / Satellite Embedding V1 Annual mean embedding
    (64-d) for a baseline year and a recent year, and
  * Dynamic World mean land-cover class probabilities for a baseline and a
    recent date window.

Earth Engine is a *batch data-acquisition* layer: this module is imported only
by the research spike and the nationwide ingestion script — never by the FastAPI
request path. ``import ee`` is deferred into the functions so the module loads
without ``earthengine-api`` installed.

Datasets:
  * ``GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL``  (CC-BY-4.0)
  * ``GOOGLE/DYNAMICWORLD/V1``                 (open)

Auth: set ``EE_SERVICE_ACCOUNT_JSON`` (path to a service-account key) and
``EE_PROJECT`` in the environment, or run ``earthengine authenticate`` once for
an interactive research account.
"""
from __future__ import annotations

import os
from typing import Any

_ALPHAEARTH = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
_DYNAMIC_WORLD = "GOOGLE/DYNAMICWORLD/V1"
_EMBED_BANDS = [f"A{i:02d}" for i in range(64)]
_DW_BANDS = [
    "water", "trees", "grass", "flooded_vegetation", "crops",
    "shrub_and_scrub", "built", "bare", "snow_and_ice",
]


def initialize(service_account_json: str | None = None, project: str | None = None) -> None:
    """Initialise Earth Engine. Raises ImportError if earthengine-api is absent."""
    import ee  # deferred — keeps the module importable without EE installed

    service_account_json = service_account_json or os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    project = project or os.environ.get("EE_PROJECT")
    if service_account_json:
        # Support either a path to the key file or inline JSON.
        if os.path.isfile(service_account_json):
            email = _read_sa_email(service_account_json)
            credentials = ee.ServiceAccountCredentials(email, key_file=service_account_json)
        else:
            email = _read_sa_email_inline(service_account_json)
            credentials = ee.ServiceAccountCredentials(email, key_data=service_account_json)
        ee.Initialize(credentials, project=project)
    else:
        ee.Initialize(project=project)


def _read_sa_email(path: str) -> str:
    import json
    with open(path) as fh:
        return json.load(fh)["client_email"]


def _read_sa_email_inline(blob: str) -> str:
    import json
    return json.loads(blob)["client_email"]


def _grid_cells(bbox: list[float], grid_n: int):
    """Yield (row, col, ee.Geometry.Rectangle) for each grid cell."""
    import ee
    min_lon, min_lat, max_lon, max_lat = bbox
    lon_step = (max_lon - min_lon) / grid_n
    lat_step = (max_lat - min_lat) / grid_n
    for row in range(grid_n):
        for col in range(grid_n):
            c0 = min_lon + col * lon_step
            r0 = min_lat + row * lat_step
            rect = ee.Geometry.Rectangle([c0, r0, c0 + lon_step, r0 + lat_step])
            yield row, col, rect


def _annual_embedding(year: int):
    import ee
    start = f"{year}-01-01"
    end = f"{year + 1}-01-01"
    return ee.ImageCollection(_ALPHAEARTH).filterDate(start, end).first().select(_EMBED_BANDS)


def _dw_composite(start: str, end: str):
    import ee
    return ee.ImageCollection(_DYNAMIC_WORLD).filterDate(start, end).select(_DW_BANDS).mean()


def fetch_cells(request: Any) -> list[dict[str, Any]]:
    """Return per-cell observations for ``run_embedding_ingest``.

    ``request`` is an ``EmbeddingIngestRequest`` (duck-typed: ``bbox``,
    ``grid_resolution``, ``baseline_year``, ``recent_year`` and optional
    ``dw_*`` date windows). Uses one ``reduceRegions`` per layer over a
    FeatureCollection of grid-cell polygons, then assembles the cell list.
    """
    import ee

    bbox = list(request.bbox)
    grid_n = int(request.grid_resolution)

    features, index = [], []
    for row, col, rect in _grid_cells(bbox, grid_n):
        features.append(ee.Feature(rect, {"row": row, "col": col}))
        index.append((row, col))
    fc = ee.FeatureCollection(features)

    emb0 = _annual_embedding(request.baseline_year)
    emb1 = _annual_embedding(request.recent_year)
    mean = ee.Reducer.mean()

    def reduce_to_map(image, scale):
        reduced = image.reduceRegions(collection=fc, reducer=mean, scale=scale).getInfo()
        out = {}
        for feat in reduced["features"]:
            props = feat["properties"]
            out[(props["row"], props["col"])] = props
        return out

    emb0_map = reduce_to_map(emb0, 10)
    emb1_map = reduce_to_map(emb1, 10)

    dw0_map = dw1_map = {}
    if request.dw_baseline_start and request.dw_baseline_end:
        dw0_map = reduce_to_map(
            _dw_composite(str(request.dw_baseline_start.date()), str(request.dw_baseline_end.date())), 10
        )
    if request.dw_recent_start and request.dw_recent_end:
        dw1_map = reduce_to_map(
            _dw_composite(str(request.dw_recent_start.date()), str(request.dw_recent_end.date())), 10
        )

    def emb_vec(props):
        if not props:
            return None
        vec = [props.get(b) for b in _EMBED_BANDS]
        return vec if all(v is not None for v in vec) else None

    def dw_map(props):
        if not props:
            return None
        out = {b: props.get(b) for b in _DW_BANDS if props.get(b) is not None}
        return out or None

    cells: list[dict[str, Any]] = []
    for row, col in index:
        cells.append({
            "row": row,
            "col": col,
            "embedding_baseline": emb_vec(emb0_map.get((row, col))),
            "embedding_recent": emb_vec(emb1_map.get((row, col))),
            "dw_baseline": dw_map(dw0_map.get((row, col))),
            "dw_recent": dw_map(dw1_map.get((row, col))),
        })
    return cells
