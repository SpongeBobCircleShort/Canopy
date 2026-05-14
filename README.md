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

Canopy now enforces organization scoping for regions, sensors, clip uploads, alerts, alert status updates, and CSV exports. Admin users can create/list/revoke member invites, create regions/sensors, update statuses, and export CSV. Members can read org data and upload clips to sensors in their org. Team/project hierarchy and fine-grained role policies are deferred.
