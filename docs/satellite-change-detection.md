# Satellite Change Detection: Telling Harmful Loss From Benign Change

Canopy ingests Sentinel-2 imagery and flags **canopy loss**, but a raw NDVI drop
between two dates has four very different possible causes. Only one is worth a
ranger's time. This document explains how the pipeline
([`sentinel_ingestion.py`](../api/app/services/sentinel_ingestion.py)) separates
them.

## The four causes of an NDVI drop

| Cause | Benign? | Signature | Discriminator |
| --- | --- | --- | --- |
| **Cloud / shadow / cirrus** | Artifact | Sharp drop, transient, follows cloud shapes | **Per-pixel SCL masking** |
| **Weather / climate / season** | Benign | Affects the **whole AOI uniformly** (drought, haze, sun angle, dry season) | **Regional common-mode removal** |
| **Not forest** (water, cropland, bare) | N/A | Low or wildly seasonal baseline NDVI | **Baseline-forest gate** |
| **Logging / clearing / fire / roads** | **Harmful** | **Local, abrupt, spatially contiguous** drop beyond the regional trend | What survives the three filters, **boosted by spatial clustering** |

## 1. Cloud masking (SCL)

Sentinel-2 L2A ships a Scene Classification Layer (SCL). Before a grid cell's
NDVI is computed for a scene, pixels classified as cloud (8, 9), cloud shadow
(3), cirrus (10), saturated (1), dark area (2) or no-data (0) are dropped; only
vegetation/bare/water/unclassified/snow (4, 5, 6, 7, 11) count. A cell needs at
least `min_valid_fraction` clear pixels to be usable in that scene; otherwise it
is **no-data** for that scene rather than a misleading cloudy average. Multi-scene
compositing then takes the per-cell median over only the clear observations.

If SCL is unavailable or unparseable, the pipeline degrades gracefully to a
uniform validity proxy from the scene-level `eo:cloud_cover` — it never trusts
unmasked cloudy pixels silently. `valid_fraction` is recorded on every detection.

## 2. Regional common-mode removal (weather/climate/season)

This is the key idea. Weather, drought, atmospheric haze, sun-angle and seasonal
phenology shift **every cell in the AOI together**. Real logging is a **local**
event. So instead of flagging on the raw drop, we compute the **regional median
ΔNDVI** across all forest cells and flag on the **local residual**:

```
local_residual = cell_delta − regional_median_delta
```

A cell that dropped about as much as its whole region (`local_residual` near 0)
is marked `likely_regional` and scored down — it's probably weather/season. A
cell that dropped far more than the region is the signal. The next layer
(temporal persistence, below) confirms it.

## 3. Baseline-forest gate

Only cells whose **baseline NDVI ≥ `forest_baseline_min`** (default 0.4) are
considered. This removes water, bare ground, settlements, and most cropland
(which is either low-NDVI off-season or excluded for never having been forest),
so we don't "detect" loss where there was no canopy to begin with.

## 4. Spatial coherence

Deforestation forms contiguous patches with sharp edges; sensor/atmospheric noise
is salt-and-pepper. Each loss cell's count of neighboring loss cells
(`neighbor_loss_count`) boosts confidence, and a cell only escalates from
`ndvi_drop` to `canopy_loss` when it is both a strong local anomaly and part of a
cluster.

## Confidence and provenance

Each detection's confidence combines clear-pixel support, local-anomaly strength,
and spatial clustering, and every change carries a `discriminators` block in its
metadata so the result is auditable on the map and in CSV export:

```json
"discriminators": {
  "valid_fraction": 0.97,
  "baseline_clear_obs": 3,
  "observation_clear_obs": 2,
  "regional_median_delta": -0.05,
  "local_residual": -0.55,
  "neighbor_loss_count": 4,
  "baseline_was_forest": true,
  "likely_regional": false
}
```

## What this does not yet do (next layers)

- **Temporal persistence / confirmation.** The strongest discriminator against
  transient cloud/weather is *time*: real clearing stays low across multiple
  consecutive clear observations, while artifacts recover. GLAD/RADD-style alerts
  confirm only after N low looks. This needs a time series rather than a single
  baseline-vs-observation pair — the planned next layer.
- **Cause attribution (logging vs road vs fire).** NDVI alone cannot fully
  separate harmful causes; that needs shape/context (geometric vs irregular
  edges, proximity to infrastructure), a burn index (NBR) for fire, or higher-res
  imagery. For alerting, all are real canopy loss; attribution is an enrichment.
- **Seasonal (harmonic) baselines.** Comparing the same season year-over-year, or
  fitting a per-cell seasonal model, removes phenology more precisely than the
  regional common-mode approximation.
