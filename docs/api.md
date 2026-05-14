# Canopy API Design

All routes are prefixed with `/api`.

## Health

- `GET /api/health` returns service status.

## Auth

- `POST /api/auth/signup` accepts `name`, `email`, `password`, and either `organization_name` for a new organization or `invite_token` to join an existing organization. New-organization signup creates the organization and gives the first user the `admin` role; invite signup assigns the invited role, currently `member`.
- `POST /api/auth/login` accepts email and password, verifies the stored password hash, and returns a signed bearer token.
- `GET /api/auth/me` returns the authenticated user profile, role, organization id, and organization details.

Tokens include `sub`, `user_id`, `email`, `role`, and `org_id` claims. If `invite_token` is provided, `organization_name` is rejected; if neither is provided, signup returns a validation error.

## Organizations

- `GET /api/organizations` returns organizations visible to the user. Admin users can list organizations; member users receive their own organization only.
- `POST /api/organizations` creates an organization. Requires `admin`.
- `GET /api/organizations/{org_id}` returns an organization if the user is an admin or belongs to that organization.
- `POST /api/organizations/{org_id}/invites` creates a member invite for the current admin's organization and returns the token/accept URL for local development.
- `GET /api/organizations/{org_id}/invites` lists invites for the current admin's organization without returning tokens.
- `POST /api/organizations/{org_id}/invites/{invite_id}/revoke` revokes a pending invite.

## Regions

- `GET /api/regions` lists regions for the authenticated user's organization.
- `POST /api/regions` creates a region in the authenticated user's organization. Requires `admin`.
- `GET /api/regions/{region_id}` returns a region only if it belongs to the authenticated user's organization.

Region payloads accept `name`, optional `description`, and optional `boundary` as GeoJSON text. PostgreSQL/PostGIS stores the boundary as polygon geometry; SQLite stores boundary text for test/lightweight development.

## Sensors

- `GET /api/sensors` lists sensors for the authenticated user's organization.
- `POST /api/sensors` creates a persisted sensor in the authenticated user's organization. Requires `admin`.
- If `region_id` is provided, it must belong to the same organization as the user.

## Alerts

- `GET /api/alerts` lists alerts for the authenticated user's organization.
- `GET /api/alerts?status=open&type=audio&sensor_id=1` filters alerts by lifecycle status, alert type, and sensor; `sensor_id` must belong to the same organization.
- `GET /api/alerts?start_time=2026-05-01T00:00:00Z&end_time=2026-05-14T00:00:00Z` filters by creation time.
- `GET /api/alerts?bbox=min_lon,min_lat,max_lon,max_lat` filters by bounding box. SQLite uses latitude/longitude comparisons; PostGIS uses `ST_MakeEnvelope` against alert geometry.
- `POST /api/alerts` creates a persisted alert in the authenticated user's organization. Requires `admin`.
- `GET /api/alerts/{alert_id}` returns alert details only inside the authenticated user's organization.
- `PATCH /api/alerts/{alert_id}/status` updates alert lifecycle status. Requires `admin`. Allowed statuses are `open`, `acknowledged`, `investigating`, `resolved`, and `dismissed`; an optional `note` can be provided.
- `GET /api/alerts/export?format=csv` returns organization-scoped filtered alert data as a downloadable CSV. Requires `admin`.

## Audio clips

- `POST /api/clips/upload` accepts multipart audio upload with required `sensor_id`, persists an audio clip record, runs the placeholder classifier service, and creates a placeholder audio alert at the sensor location. Requires authentication.
- The linked sensor must belong to the authenticated user's organization.
- Supported MVP extensions are `.wav`, `.flac`, `.mp3`, `.ogg`, and `.m4a`.

## Permission matrix

| Capability | Admin | Member |
| --- | --- | --- |
| Read own organization profile | Yes | Yes |
| Create organizations | Yes | No |
| Create/list/revoke member invites | Yes | No |
| Read own org regions/sensors/alerts | Yes | Yes |
| Create regions | Yes | No |
| Create sensors | Yes | No |
| Upload clips to own org sensors | Yes | Yes |
| Update alert status | Yes | No |
| Export alert CSV | Yes | No |
| Read satellite changes | Yes | Yes |
| Create/delete satellite changes | Yes | No |
| Run fusion | Yes | No |

Tenant isolation is enforced for regions, sensors, clips, alerts, satellite changes, fusion runs, status updates, CSV export, and organization invites. Invite tokens are stored raw for the MVP so local demos can copy them from the API response; production should store hashed invite tokens and send invite links by email. Team/project hierarchy and fine-grained field permissions remain deferred.

## Persistence

The Docker stack uses PostgreSQL/PostGIS. Tests and simple local runs can use SQLite by setting `DATABASE_URL=sqlite:///./canopy-dev.db`; the API initializes a lightweight SQLite schema automatically for that mode. SQLite stores region boundaries as text; PostGIS stores them as geometry.

## Future routes

- `GET /api/satellite`
- `POST /api/satellite/analyze`
- `POST /api/labels`

## Satellite changes (manual/stub MVP)

This is a manual/stub satellite-change workflow. Real Sentinel/NDVI processing is deferred.

- `GET /api/satellite-changes` lists satellite-change events for the authenticated user's organization. Admins and members can read their own org events.
- `POST /api/satellite-changes` creates a manual satellite-change event. Requires `admin`.
- `GET /api/satellite-changes/{change_id}` returns an event only if it belongs to the authenticated user's organization.
- `DELETE /api/satellite-changes/{change_id}` deletes an event in the authenticated user's organization. Requires `admin`.

Create payload fields include `region_id`, `source` (defaults to `manual`), `change_type` (`ndvi_drop`, `canopy_loss`, `vegetation_stress`, `burn_scar`, or `unknown`), `severity_score` from `0.0` to `1.0`, `confidence` from `0.0` to `1.0`, optional observation/baseline timestamps, `latitude`, `longitude`, `geometry`, `description`, and `metadata`. If `region_id` is provided, it must belong to the current organization.

Example:

```bash
curl -s -X POST http://localhost:8000/api/satellite-changes \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"region_id\":$REGION_ID,\"source\":\"manual\",\"change_type\":\"canopy_loss\",\"severity_score\":0.8,\"confidence\":0.9,\"latitude\":-3.4654,\"longitude\":-62.2160,\"description\":\"Manual canopy-loss observation near FLU-Demo\"}" \
  | python -m json.tool
```

## Fusion

- `POST /api/fusion/run` runs the admin-only rule-based fusion service for the current organization.
- The service only reads acoustic alerts and satellite changes in the authenticated user's organization, respects `distance_meters`, `time_window_days`, `min_acoustic_confidence`, and `min_satellite_severity`, and avoids duplicate fused alerts for the same acoustic/satellite pair.

Default request:

```json
{
  "time_window_days": 14,
  "distance_meters": 500,
  "min_acoustic_confidence": 0.65,
  "min_satellite_severity": 0.3
}
```

Fusion uses this score:

```text
fusion_score =
  0.45 * acoustic_confidence
  + 0.35 * satellite severity_score
  + 0.10 * satellite confidence
  + 0.10 * recurrence_bonus
```

Fused alert metadata includes `acoustic_alert_id`, `satellite_change_id`, `acoustic_confidence`, `satellite_severity_score`, `satellite_confidence`, `distance_meters`, `fusion_score`, and `fusion_rule_version`.

Examples:

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.org","password":"correct-horse-battery"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# Create a manual satellite change
SATELLITE_CHANGE_ID=$(curl -s -X POST http://localhost:8000/api/satellite-changes \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"region_id\":$REGION_ID,\"source\":\"manual\",\"change_type\":\"canopy_loss\",\"severity_score\":0.8,\"confidence\":0.9,\"latitude\":-3.4654,\"longitude\":-62.2160,\"description\":\"Manual canopy-loss observation near FLU-Demo\"}" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# Run fusion
curl -s -X POST http://localhost:8000/api/fusion/run \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"time_window_days":14,"distance_meters":500,"min_acoustic_confidence":0.65,"min_satellite_severity":0.3}' \
  | python -m json.tool

# List fused alerts
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts?type=fusion' | python -m json.tool

# Export CSV with fusion metadata
curl -L -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/alerts/export?format=csv' -o canopy-alerts-with-fusion.csv
```

## Browser demo flow

1. Sign up or log in from the React dashboard.
2. Create a region.
3. Create a sensor.
4. Upload an audio clip, such as a file named `chainsaw.wav`, to generate an acoustic alert.
5. Create a manual satellite-change event near the sensor.
6. Run fusion.
7. Inspect the fused alert in the dashboard list/map.
8. Export alert CSV and verify the fusion metadata columns.

## NDVI ingestion

This is CSV/sample-based NDVI ingestion. Live Sentinel/Google Earth Engine integration is deferred.

- `POST /api/ndvi/upload-csv` accepts multipart CSV upload. Requires `admin`.
- `GET /api/ndvi/batches` lists NDVI ingestion batches for the authenticated user's organization. Admins and members can list.
- `GET /api/ndvi/batches/{batch_id}` returns one org-scoped batch.

Upload form fields:

- `file`: CSV file.
- `region_id`: optional region to assign to generated satellite-change events. It must belong to the current organization.
- `loss_threshold`: optional, default `-0.15`.
- `default_confidence`: optional, default `0.75`.

Required CSV columns are `latitude`, `longitude`, `baseline_ndvi`, and `recent_ndvi`. Optional columns are `region_id`, `baseline_start`, `baseline_end`, `observation_start`, `observation_end`, `description`, and `confidence`.

For each row:

```text
ndvi_delta = recent_ndvi - baseline_ndvi
severity_score = min(abs(ndvi_delta) / 0.5, 1.0)
```

Rows are skipped unless `ndvi_delta <= loss_threshold`. Generated satellite changes use `source=csv_ndvi`, `change_type=ndvi_drop`, and metadata containing `baseline_ndvi`, `recent_ndvi`, `ndvi_delta`, `loss_threshold`, `ingestion_batch_id`, and `row_number`.

Example:

```bash
curl -s -X POST http://localhost:8000/api/ndvi/upload-csv \
  -H "Authorization: Bearer $TOKEN" \
  -F "region_id=$REGION_ID" \
  -F 'loss_threshold=-0.15' \
  -F 'default_confidence=0.75' \
  -F 'file=@docs/sample-data/ndvi_sample.csv;type=text/csv' \
  | python -m json.tool

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/ndvi/batches | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/satellite-changes | python -m json.tool
curl -s -X POST http://localhost:8000/api/fusion/run \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"time_window_days":14,"distance_meters":500,"min_acoustic_confidence":0.65,"min_satellite_severity":0.3}' \
  | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" 'http://localhost:8000/api/alerts?type=fusion' | python -m json.tool
```
