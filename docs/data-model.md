# Canopy Data Model

The initial PostgreSQL/PostGIS schema is defined in `api/migrations/001_initial_schema.sql`; the SQLite test/dev schema is initialized in `api/app/db.py`.

## Entities

- `organizations`: Tenant boundary for conservation groups and partners. Fields include `id`, `name`, optional `description`, `created_at`, and `updated_at`.
- `users`: Authenticated users with `organization_id` membership and `admin`/`member` roles.
- `organization_invites`: Admin-created invite records with org, email, role, token, pending/accepted/revoked/expired status, inviter, expiration, and acceptance timestamps.
- `regions`: Organization-scoped protected areas or monitoring polygons. PostGIS stores `boundary` as polygon geometry; SQLite stores `boundary_geojson` text.
- `sensors`: Organization-scoped forest listening units stored as PostGIS points or SQLite latitude/longitude values. Sensors may belong to a region.
- `audio_clips`: Organization-scoped uploaded or ingested audio files with sensor and capture metadata.
- `audio_labels`: Human or model labels attached to clips.
- `satellite_images`: Satellite capture metadata and NDVI raster/object references for future work.
- `alerts`: Organization-scoped operational threats from audio, satellite, or fused sources.

## Spatial design

PostGIS geometry columns use SRID 4326 for MVP interoperability with Leaflet, GeoJSON, and common GIS tools. Spatial indexes are created for regions, sensors, and alerts. SQLite mode stores coordinates as numeric columns and uses bounding-box comparisons in repository filters.

## Runtime persistence

The FastAPI application writes organizations, regions, sensors, alerts, users, and audio clip metadata through repository functions in `api/app/repositories.py`. PostgreSQL/PostGIS stores production geometries, while SQLite stores latitude/longitude columns and GeoJSON text for automated tests and lightweight local development.

## Alert lifecycle fields

Alerts include lifecycle `status`, optional `status_note`, `created_at`, and `updated_at`. Audio alerts may include `classifier_label`, `classifier_confidence`, and `classifier_model_version` so a real classifier can be plugged in later without changing the API response shape.

## Organization and roles

Users include `role` and nullable `organization_id`, though the MVP signup flow creates an organization and assigns the first user as `admin`. Authentication tokens carry these claims. Region, sensor, clip, alert, status update, and CSV export repository calls are scoped by `org_id`.


## Invite model

Organization admins can create pending member invites. Invite acceptance through signup validates token status, expiration, and email match, then creates the user in the existing organization and marks the invite accepted. Raw invite token storage is an MVP limitation documented for replacement with hashed tokens before production use.

## NDVI ingestion batches

`ndvi_ingestion_batches` tracks CSV/sample NDVI ingestion runs that generate satellite-change events.

| Field | Notes |
| --- | --- |
| `id` | Batch id |
| `org_id` | Tenant owner |
| `region_id` | Optional region context for generated changes |
| `uploaded_by_user_id` | Admin user that uploaded the CSV |
| `source_type` | `csv` for the MVP |
| `filename` | Original uploaded filename |
| `status` | `pending`, `processed`, or `failed` |
| `row_count` | CSV data rows parsed |
| `created_change_count` | Satellite-change events created from rows beyond threshold |
| `error_message` | Validation/processing error if failed |
| `metadata` | JSON settings such as `loss_threshold`, `default_confidence`, and created ids |
| `created_at` / `processed_at` | Batch lifecycle timestamps |

Generated `satellite_change_events` use `source=csv_ndvi`, `change_type=ndvi_drop`, and metadata with NDVI provenance (`baseline_ndvi`, `recent_ndvi`, `ndvi_delta`, `loss_threshold`, `ingestion_batch_id`, `row_number`).
