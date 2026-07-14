"""Phase-0 signal spike: does foundation-model change detection separate real
forest loss from stable forest, and does it agree with Hansen Global Forest
Change?

Runs the *production* scoring (``app.services.embedding_ingestion``) over a known
loss AOI and a known stable-forest AOI, prints separation metrics, and compares
the ranking against Hansen ``lossyear``. Credential-gated: if Earth Engine is
not configured it prints setup instructions and exits 0 (so it never breaks CI).

Usage:
    EE_PROJECT=your-project python research/satellite/spike.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Import the production scoring so the spike validates exactly what ships.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "api"))

from app.schemas import EmbeddingIngestRequest  # noqa: E402
from app.services.embedding_ingestion import embedding_change, run_embedding_ingest  # noqa: E402

import ee_fetch  # noqa: E402  (same directory)

# Small AOIs (≈0.2°). Tune to validated ground truth before trusting numbers.
AOIS = {
    "loss_site (Similipal fringe, Odisha)": [86.20, 21.50, 86.40, 21.70],
    "stable_site (Namdapha interior, Arunachal)": [96.30, 27.40, 96.50, 27.60],
}
BASELINE_YEAR = 2019
RECENT_YEAR = 2023


def _capturing_create_fn():
    payloads: list = []

    def _create(_org_id, payload):
        payloads.append(payload)
        return SimpleNamespace(id=len(payloads))

    return _create, payloads


def _hansen_loss_fraction(bbox: list[float], y0: int, y1: int) -> float | None:
    """Mean fraction of pixels in the AOI with Hansen lossyear in (y0, y1]."""
    try:
        import ee
        gfc = ee.Image("UMD/hansen/global_forest_change_2023_v1_11").select("lossyear")
        mask = gfc.gt(y0 - 2000).And(gfc.lte(y1 - 2000))
        rect = ee.Geometry.Rectangle(bbox)
        val = mask.reduceRegion(ee.Reducer.mean(), rect, scale=30, maxPixels=1e9).getInfo()
        return val.get("lossyear")
    except Exception as exc:  # noqa: BLE001
        print(f"  (Hansen comparison unavailable: {exc})")
        return None


def main() -> int:
    try:
        ee_fetch.initialize()
    except ImportError:
        print(
            "earthengine-api is not installed.\n"
            "  pip install -r research/satellite/requirements-satellite.txt\n"
            "  earthengine authenticate   # or set EE_SERVICE_ACCOUNT_JSON + EE_PROJECT"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            f"Earth Engine init failed: {exc}\n"
            "Register a (free, non-commercial) Earth Engine account, then either run\n"
            "`earthengine authenticate` or set EE_SERVICE_ACCOUNT_JSON + EE_PROJECT."
        )
        return 0

    print(f"AlphaEarth {BASELINE_YEAR}→{RECENT_YEAR} semantic change + Dynamic World transition\n")
    results = {}
    for name, bbox in AOIS.items():
        request = EmbeddingIngestRequest(
            bbox=bbox, baseline_year=BASELINE_YEAR, recent_year=RECENT_YEAR, grid_resolution=8,
        )
        cells = ee_fetch.fetch_cells(request)
        create_fn, payloads = _capturing_create_fn()
        resp = run_embedding_ingest(request, org_id=0, create_satellite_change_fn=create_fn, fetch_fn=lambda _r, c=cells: c)
        changes = [
            ch
            for cell in cells
            if (ch := embedding_change(cell.get("embedding_baseline"), cell.get("embedding_recent"))) is not None
        ]
        mean_change = sum(changes) / len(changes) if changes else 0.0
        flagged = resp.created_change_count
        mean_sev = (sum(p.severity_score for p in payloads) / len(payloads)) if payloads else 0.0
        hansen = _hansen_loss_fraction(bbox, BASELINE_YEAR, RECENT_YEAR)
        results[name] = (mean_change, flagged, mean_sev, hansen)
        print(f"{name}")
        print(f"  mean embedding change : {mean_change:.3f}")
        print(f"  flagged cells         : {flagged}/{len(cells)}")
        print(f"  mean severity         : {mean_sev:.3f}")
        print(f"  Hansen loss fraction  : {hansen if hansen is None else f'{hansen:.3f}'}\n")

    names = list(results)
    if len(names) == 2:
        loss, stable = results[names[0]][0], results[names[1]][0]
        verdict = "PASS — loss site ranks higher" if loss > stable else "FAIL — no separation"
        print(f"Separation: loss {loss:.3f} vs stable {stable:.3f} → {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
