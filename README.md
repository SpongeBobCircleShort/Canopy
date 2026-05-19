# Canopy

Canopy is an open-source forest monitoring platform scaffold for combining acoustic threat detection, satellite vegetation analysis, and geospatial alerts for conservation teams.

## What is included

- `api/`: FastAPI backend with JWT auth, organizations, regions, org-scoped sensors, alerts, and audio clip endpoints.
- `frontend/`: React + Vite dashboard scaffold with auth, region/sensor creation, upload, lifecycle, export, and map UI components.
- `api/migrations/`: Initial PostgreSQL/PostGIS schema SQL for the MVP data model.
- `docker-compose.yml`: Local development stack with PostGIS, API, and frontend services.
- `docs/`: Product, architecture, API, and data model documentation.
- `.github/workflows/ci.yml`: Baseline CI checks for backend and frontend tests.

## Quick start with Docker

```bash
cp .env.example .env
docker compose up --build
```

Services:

- API: <http://localhost:8000/api/health>
- Frontend: <http://localhost:5173>
- PostGIS: `localhost:5432`

## Backend development

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./canopy-dev.db
pytest
uvicorn app.main:app --reload
```

## Frontend development

```bash
cd frontend
npm install
npm test
npm run dev
```

## Documentation

- [Product specification](docs/product-spec.md)
- [Architecture](docs/architecture.md)
- [API design](docs/api.md)
- [Data model](docs/data-model.md)

## Organization-scoped MVP API flow

1. Create a user with `POST /api/auth/signup` and `organization_name`. This creates the organization and makes the first user an `admin`.
2. Use that token to create org-scoped regions with `POST /api/regions`.
3. Create sensors in the organization, optionally linked to a region, with `POST /api/sensors`.
4. Upload audio with `POST /api/clips/upload` and a `sensor_id` multipart field.
5. Review organization-scoped alerts through `GET /api/alerts` or the dashboard.
6. Update alert lifecycle status with `PATCH /api/alerts/{alert_id}/status`.
7. Export organization-scoped alerts with `GET /api/alerts/export?format=csv`.

The API uses PostgreSQL/PostGIS in Docker and can use SQLite for tests or lightweight local development by setting `DATABASE_URL=sqlite:///./canopy-dev.db`.

### Optional local audio model backend

The API defaults to the deterministic placeholder audio classifier. To test the Phase 3A research model locally, install the separate audio dependencies and point the API at an ignored model artifact directory:

```bash
pip install -r ../research/audio/requirements-audio.txt
export AUDIO_CLASSIFIER_BACKEND=local_model
export AUDIO_MODEL_DIR=../models/audio/threat_cnn_v1
```

`AUDIO_CLASSIFIER_BACKEND=placeholder` remains the default. The local backend loads `model.pt`, `labels.json`, and threshold recommendations from `test_metrics.json` or `metrics.json`; trained model files stay out of git under `models/audio/`.

## MVP local demo flow

The MVP flow can run against Docker/PostGIS or against SQLite for lightweight development. For SQLite, start the API from `api/` with:

```bash
export DATABASE_URL=sqlite:///./canopy-dev.db
export AUDIO_STORAGE_PATH=./canopy-audio
uvicorn app.main:app --reload
```

Then run these commands from the repository root:

```bash
# 1. Sign up, create an organization, and capture an admin token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo Ranger","email":"demo@example.org","password":"correct-horse-battery","organization_name":"Demo Conservation Org"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# 2. Log in if the user already exists
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.org","password":"correct-horse-battery"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# 3. Create an organization-scoped region
REGION_ID=$(curl -s -X POST http://localhost:8000/api/regions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"North Sector","description":"Demo patrol area"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# 4. Create a geolocated sensor in the region
SENSOR_ID=$(curl -s -X POST http://localhost:8000/api/sensors \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"FLU-Demo\",\"device_type\":\"forest-listening-unit\",\"region_id\":$REGION_ID,\"location\":{\"lat\":-3.4653,\"lon\":-62.2159}}" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# 5. Upload an audio clip linked to the sensor
printf 'RIFF....WAVE' > /tmp/chainsaw-demo.wav
ALERT_ID=$(curl -s -X POST http://localhost:8000/api/clips/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "sensor_id=$SENSOR_ID" \
  -F 'file=@/tmp/chainsaw-demo.wav;type=audio/wav' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["generated_alert"]["id"])')

# 6. List org-scoped alerts, including bbox/type/status filters when needed
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts?type=audio&bbox=-63,-4,-62,-3' | python -m json.tool

# 7. Update alert lifecycle status
curl -s -X PATCH "http://localhost:8000/api/alerts/$ALERT_ID/status" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status":"investigating","note":"Demo ranger dispatched"}' \
  | python -m json.tool

# 8. Export org-scoped filtered alerts as CSV
curl -L -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts/export?format=csv&type=audio' -o canopy-alerts.csv
```

## Organization invite flow

Admins can invite members into an existing organization without creating a new organization for each user. Invite tokens are returned once at creation time for local development; the MVP stores raw invite tokens, so production deployments should replace this with hashed tokens and email delivery.

```bash
# Admin creates an invite for their organization
ORG_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/auth/me \
  | python -c 'import json,sys; print(json.load(sys.stdin)["org_id"])')

INVITE_TOKEN=$(curl -s -X POST "http://localhost:8000/api/organizations/$ORG_ID/invites" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"email":"member@example.org","role":"member"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')

# Invited member signs up into the existing organization
MEMBER_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Member Ranger\",\"email\":\"member@example.org\",\"password\":\"correct-horse-battery\",\"invite_token\":\"$INVITE_TOKEN\"}" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# Member can read org-scoped dashboard data
curl -s -H "Authorization: Bearer $MEMBER_TOKEN" http://localhost:8000/api/sensors | python -m json.tool

# Admin lists and revokes pending invites
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/organizations/$ORG_ID/invites" | python -m json.tool
curl -s -X POST -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/organizations/$ORG_ID/invites/INVITE_ID/revoke" | python -m json.tool
```

## Current RBAC scope

Canopy now enforces organization scoping for regions, sensors, clip uploads, alerts, satellite changes, fusion runs, alert status updates, and CSV exports. Admin users can create/list/revoke member invites, create regions/sensors/satellite changes, run fusion, update statuses, and export CSV. Members can read org data and satellite changes and upload clips to sensors in their org. Team/project hierarchy and fine-grained role policies are deferred.

## Manual satellite-change + fusion MVP

This is a manual/stub satellite-change workflow. Real Sentinel/NDVI processing is deferred. The browser dashboard lets admins create a satellite-change event by hand near a sensor, then run the lightweight fusion rule to link that event with acoustic alerts from uploaded clips. No Earth Engine, raster, GDAL, or real ML dependencies are included.

Fusion uses this rule:

```text
fusion_score =
  0.45 * acoustic_confidence
  + 0.35 * satellite severity_score
  + 0.10 * satellite confidence
  + 0.10 * recurrence_bonus
```

The created fused alert stores provenance in `metadata`: `acoustic_alert_id`, `satellite_change_id`, `acoustic_confidence`, `satellite_severity_score`, `satellite_confidence`, `distance_meters`, `fusion_score`, and `fusion_rule_version`. Alert CSV export includes these fields where available.

### Browser demo flow

1. Open <http://localhost:5173> and sign up or log in.
2. Create a region.
3. Create a sensor in or near that region.
4. Upload a demo audio file named `chainsaw.wav` to generate an acoustic alert from the placeholder classifier.
5. Use the **Manual satellite change** panel to create a nearby `canopy_loss`, `ndvi_drop`, or other stub satellite-change event.
6. Click **Run Fusion** as an admin.
7. Inspect the fused alert in the alert list and map. Fused alerts display `fusion_score`, `acoustic_alert_id`, and `satellite_change_id`.
8. Click **Export alerts CSV** to download alerts with fusion metadata columns.

### Curl satellite-change and fusion demo

The earlier MVP curl flow signs up/logs in, creates a region/sensor, and uploads a clip. Continue from the same `TOKEN`, `REGION_ID`, and `SENSOR_ID` values:

```bash
# Login and capture a token if needed
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.org","password":"correct-horse-battery"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# Create a manual/stub satellite-change event near the demo sensor
SATELLITE_CHANGE_ID=$(curl -s -X POST http://localhost:8000/api/satellite-changes \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"region_id\":$REGION_ID,\"source\":\"manual\",\"change_type\":\"canopy_loss\",\"severity_score\":0.8,\"confidence\":0.9,\"latitude\":-3.4654,\"longitude\":-62.2160,\"description\":\"Manual canopy-loss observation near FLU-Demo\"}" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# Run the default fusion rule
curl -s -X POST http://localhost:8000/api/fusion/run \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"time_window_days":14,"distance_meters":500,"min_acoustic_confidence":0.65,"min_satellite_severity":0.3}' \
  | python -m json.tool

# List fused alerts
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts?type=fusion' | python -m json.tool

# Export CSV with fusion metadata columns
curl -L -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts/export?format=csv' -o canopy-alerts-with-fusion.csv
```

## Verified MVP Demo

Use this checklist to validate the demo-ready manual satellite-change + fusion MVP in an environment with package registry and Docker access.

### Install dependencies

```bash
cd api
python -m pip install -r requirements.txt -r requirements-dev.txt

cd ../frontend
npm install
```

### Run tests and builds

```bash
# Backend
python -m compileall api/app api/tests
cd api && pytest -q

# Frontend
cd ../
python -m json.tool frontend/package.json >/tmp/package.json.valid
cd frontend && npm test
cd frontend && npm run build

# Repo/Docker configuration
cd ../
git diff --check
docker compose config
```

### Run the Docker stack

```bash
docker compose up --build
```

Expected services:

- PostGIS database on `localhost:5432`
- FastAPI API on <http://localhost:8000>
- React/Vite frontend on <http://localhost:5173>

### Run the API smoke-test script

With the API running locally, run:

```bash
scripts/demo_mvp_flow.sh
```

The script uses safe generated local demo credentials, fails fast on HTTP or assertion errors, prints the key `org_id`, `region_id`, `sensor_id`, `acoustic_alert_id`, `satellite_change_id`, and `fused_alert_id`, and writes the exported CSV to `demo-output/canopy-alerts-with-fusion.csv` by default.

Optional environment overrides:

```bash
API_BASE_URL=http://localhost:8000 \
DEMO_EMAIL=canopy-demo@example.org \
OUTPUT_DIR=demo-output \
scripts/demo_mvp_flow.sh
```

### Browser demo flow

1. Open <http://localhost:5173>.
2. Sign up or log in.
3. Create a region.
4. Create a sensor in that region.
5. Upload a small audio clip named `chainsaw.wav` to create an acoustic alert through the placeholder classifier.
6. Create a manual satellite-change event near the sensor.
7. Click **Run Fusion**.
8. Confirm the fused alert appears on the map and in the alert list with `fusion_score`, `acoustic_alert_id`, and `satellite_change_id`.
9. Export the CSV and confirm fusion metadata columns are present.

When browser automation or screenshot tooling is available, save evidence under `docs/demo/` using:

- `docs/demo/01-dashboard-acoustic-alert.png`
- `docs/demo/02-satellite-change-form.png`
- `docs/demo/03-fused-alert-map.png`
- `docs/demo/04-fused-alert-list.png`

### Known limitations

- Satellite-change events are manual/stubbed for the MVP.
- The audio classifier is a deterministic placeholder based on file names.
- Real Sentinel/NDVI processing is deferred.
- Real ML classification is deferred.

### Current validation status in this environment

The Verified MVP Demo checklist was attempted on 2026-05-14, but this execution environment still blocked package installation and Docker startup. These commands succeeded:

```bash
git diff --check
python -m compileall api/app api/tests
python -m json.tool frontend/package.json >/tmp/package.json.valid
```

These commands were blocked by environment limitations, not by code changes:

```bash
cd api && python -m pip install -r requirements.txt -r requirements-dev.txt
# Blocked while fetching fastapi==0.121.3: package index tunnel returned 403 Forbidden.

cd api && pytest -q
# Blocked because FastAPI was unavailable after dependency installation failed.

cd frontend && npm install
# Blocked while fetching @testing-library/jest-dom: npm registry returned 403 Forbidden.

cd frontend && npm test
# Blocked because vitest was unavailable after npm install failed.

cd frontend && npm run build
# Blocked because vite was unavailable after npm install failed.

docker compose config
# Blocked because docker was not installed in the environment.

docker compose up --build
# Blocked because docker was not installed in the environment.

bash scripts/demo_mvp_flow.sh
# Blocked because no API was running at http://localhost:8000 after dependency/Docker startup was blocked.
```

Expected successful smoke-script output in a fully provisioned environment includes these IDs and CSV path:

```text
Canopy MVP demo flow completed successfully.
org_id=<created org id>
region_id=<created region id>
sensor_id=<created sensor id>
acoustic_alert_id=<generated acoustic alert id>
ndvi_batch_id=<created NDVI ingestion batch id>
created_satellite_change_ids=<comma-separated generated satellite-change ids>
satellite_change_id=<first generated satellite-change id>
fused_alert_id=<created fused alert id>
csv_path=demo-output/canopy-alerts-with-fusion.csv
```

## NDVI CSV sample ingestion MVP

This is CSV/sample-based NDVI ingestion. Live Sentinel/Google Earth Engine integration is deferred. The goal is to bridge the manual satellite-change workflow with a more realistic geospatial product loop: admins can upload NDVI comparison rows for a region, and Canopy creates `satellite_change_events` automatically for vegetation-loss rows that can be fused with acoustic alerts.

### CSV format

Required columns:

- `latitude`
- `longitude`
- `baseline_ndvi`
- `recent_ndvi`

Optional columns:

- `region_id`
- `baseline_start`
- `baseline_end`
- `observation_start`
- `observation_end`
- `description`
- `confidence`

A sample file is available at [`docs/sample-data/ndvi_sample.csv`](docs/sample-data/ndvi_sample.csv).

For each row:

```text
ndvi_delta = recent_ndvi - baseline_ndvi
severity_score = min(abs(ndvi_delta) / 0.5, 1.0)
```

Vegetation loss means `ndvi_delta < 0`. Rows are skipped unless `ndvi_delta <= loss_threshold`; the default loss threshold is `-0.15`. The generated satellite-change metadata includes `baseline_ndvi`, `recent_ndvi`, `ndvi_delta`, `loss_threshold`, `ingestion_batch_id`, and `row_number`.

### Curl NDVI ingestion flow

```bash
# Upload sample NDVI CSV for an existing region
curl -s -X POST http://localhost:8000/api/ndvi/upload-csv \
  -H "Authorization: Bearer $TOKEN" \
  -F "region_id=$REGION_ID" \
  -F 'loss_threshold=-0.15' \
  -F 'default_confidence=0.75' \
  -F 'file=@docs/sample-data/ndvi_sample.csv;type=text/csv' \
  | python -m json.tool

# List ingestion batches
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/ndvi/batches | python -m json.tool

# List generated satellite changes
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/satellite-changes | python -m json.tool

# Run fusion after NDVI-generated changes exist
curl -s -X POST http://localhost:8000/api/fusion/run \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"time_window_days":14,"distance_meters":500,"min_acoustic_confidence":0.65,"min_satellite_severity":0.3}' \
  | python -m json.tool

# List fused alerts
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts?type=fusion' | python -m json.tool
```

The demo smoke script now uses the NDVI sample CSV by default:

```bash
scripts/demo_mvp_flow.sh
```
