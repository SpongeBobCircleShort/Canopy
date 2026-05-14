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

Tenant isolation is enforced for regions, sensors, clips, alerts, status updates, CSV export, and organization invites. Invite tokens are stored raw for the MVP so local demos can copy them from the API response; production should store hashed invite tokens and send invite links by email. Team/project hierarchy and fine-grained field permissions remain deferred.

## Persistence

The Docker stack uses PostgreSQL/PostGIS. Tests and simple local runs can use SQLite by setting `DATABASE_URL=sqlite:///./canopy-dev.db`; the API initializes a lightweight SQLite schema automatically for that mode. SQLite stores region boundaries as text; PostGIS stores them as geometry.

## Future routes

- `GET /api/satellite`
- `POST /api/satellite/analyze`
- `POST /api/labels`
