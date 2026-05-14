# Canopy MVP browser demo evidence

This directory is reserved for browser demo screenshots when a full local environment is available.

Suggested screenshots after launching the Docker stack or local API/frontend:

1. `01-dashboard-acoustic-alert.png` — dashboard after signup, region/sensor creation, and audio upload.
2. `02-satellite-change-form.png` — manual satellite-change form and created event list.
3. `03-fused-alert-map.png` — fused alert visible on the map with satellite-change/acoustic context.
4. `04-fused-alert-list.png` — fused alert visible in the alert list with provenance metadata.

Screenshot capture was not possible in the current environment because dependency installation and Docker access were blocked. Use the README's Verified MVP Demo steps and `scripts/demo_mvp_flow.sh` to reproduce the flow before capturing screenshots.

## Validation attempt in this environment (2026-05-14)

Screenshot capture and full browser verification were not possible in this container because the runtime prerequisites for the demo could not be installed or started:

- `cd api && python -m pip install -r requirements.txt -r requirements-dev.txt` failed while fetching `fastapi==0.121.3`: package index tunnel returned `403 Forbidden` and pip reported no available versions.
- `cd frontend && npm install` failed while fetching `@testing-library/jest-dom`: npm registry returned `403 Forbidden`.
- `docker compose config` and `docker compose up --build` failed with `docker: command not found`.
- `bash scripts/demo_mvp_flow.sh` could not connect to `http://localhost:8000` because the API was not running after the dependency/Docker blocks.

No PNG screenshots were captured in this environment. When run in an environment with package registry and Docker access, capture these files:

- `docs/demo/01-dashboard-acoustic-alert.png`
- `docs/demo/02-satellite-change-form.png`
- `docs/demo/03-fused-alert-map.png`
- `docs/demo/04-fused-alert-list.png`

## NDVI CSV ingestion demo

Sample NDVI comparison data lives at `docs/sample-data/ndvi_sample.csv`. The sample includes multiple vegetation-loss rows near the fixed demo sensor coordinates plus rows that should be skipped because the NDVI drop is below threshold, zero, or positive.

The smoke-test script uses NDVI ingestion by default:

```bash
scripts/demo_mvp_flow.sh
```

It uploads the sample CSV to `POST /api/ndvi/upload-csv`, prints `ndvi_batch_id` and `created_satellite_change_ids`, runs fusion, and exports the alert CSV.

When capturing browser screenshots for the NDVI flow, include the NDVI upload panel and batch list:

- `docs/demo/02-satellite-change-form.png` should show the NDVI upload form or generated satellite-change list.
- `docs/demo/03-fused-alert-map.png` should show the fused alert after NDVI-generated satellite changes are created.
- `docs/demo/04-fused-alert-list.png` should show fused alert metadata including NDVI provenance where visible.
