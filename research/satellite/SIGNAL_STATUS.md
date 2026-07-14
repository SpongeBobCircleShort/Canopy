# Canopy Satellite Signal Status

## Approach

Foundation-model change detection, replacing hand-rolled NDVI differencing:

- **AlphaEarth / Satellite Embedding V1 Annual** (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`,
  64-d, 10 m, annual, CC-BY-4.0) — primary signal: year-over-year semantic change
  `1 − cosine(e_baseline, e_recent)`, with regional common-mode removal.
- **Dynamic World** (`GOOGLE/DYNAMICWORLD/V1`, 10 m, near-real-time, open) —
  attribution: the dominant Trees→{bare, crops, built, shrub} transition.

Production scoring lives in `api/app/services/embedding_ingestion.py` (the single
source of truth); `research/satellite/ee_fetch.py` is the Earth Engine acquisition
layer; `research/satellite/spike.py` runs the validation below against that exact
scoring.

## Status: PENDING LIVE RUN (gated on Earth Engine registration)

The code path is complete and unit-tested offline (synthetic cells, no network —
see `api/tests/test_embedding_ingestion.py`). The live signal validation has **not**
been run yet because it needs a (free, non-commercial) Earth Engine account.

### To run the spike once EE is registered

```bash
pip install -r research/satellite/requirements-satellite.txt
earthengine authenticate            # or set EE_SERVICE_ACCOUNT_JSON + EE_PROJECT
EE_PROJECT=<your-project> python research/satellite/spike.py
```

### Pass criteria (fill in after the run)

The detector is trusted to feed real detections into the dashboard/fusion only if:

1. **Separation** — the known loss AOI's mean embedding change is materially higher
   than the stable-forest AOI's.
2. **Ground-truth agreement** — flagged cells rank with Hansen Global Forest Change
   `lossyear` for the same `baseline_year→recent_year` window.

| AOI | mean embedding change | flagged cells | mean severity | Hansen loss frac |
| --- | ---: | ---: | ---: | ---: |
| loss_site (Similipal fringe)   | _pending_ | _pending_ | _pending_ | _pending_ |
| stable_site (Namdapha interior) | _pending_ | _pending_ | _pending_ | _pending_ |

**Verdict:** _pending live run._

## Next (Phase 3)

After the spike passes, run nationwide ingestion over the Indian forest landscapes
(the same ones in `frontend/src/demoData.js`) for a baseline/recent year pair,
persist real `satellite_change` rows, and report cell-level precision/recall vs
Hansen per landscape. That per-landscape table is the satellite pass gate.
