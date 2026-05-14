from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import math
from typing import Any

from fastapi import HTTPException, status

from app.db import connection, is_sqlite
from app.schemas import (
    Alert,
    AlertCreate,
    AlertStatus,
    AlertType,
    Coordinates,
    InviteStatus,
    Organization,
    OrganizationCreate,
    OrganizationInvite,
    OrganizationInviteCreate,
    OrganizationInviteCreated,
    Region,
    RegionCreate,
    Sensor,
    SatelliteChangeCreate,
    SatelliteChangeResponse,
    SatelliteChangeSource,
    SatelliteChangeType,
    SensorCreate,
)

AlertBBox = tuple[float, float, float, float]


def _row_get(row: Any, key: str) -> Any:
    return row[key]


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _organization_from_row(row: Any) -> Organization:
    return Organization(
        id=_row_get(row, "id"),
        name=_row_get(row, "name"),
        description=_row_get(row, "description"),
        created_at=_coerce_datetime(_row_get(row, "created_at")) or datetime.now(timezone.utc),
        updated_at=_coerce_datetime(_row_get(row, "updated_at")) or datetime.now(timezone.utc),
    )




def _invite_from_row(row: Any, *, include_token: bool = False) -> OrganizationInvite | OrganizationInviteCreated:
    base = {
        "id": _row_get(row, "id"),
        "org_id": _row_get(row, "org_id"),
        "email": _row_get(row, "email"),
        "role": _row_get(row, "role"),
        "status": InviteStatus(_row_get(row, "status")),
        "invited_by_user_id": _row_get(row, "invited_by_user_id"),
        "created_at": _coerce_datetime(_row_get(row, "created_at")) or datetime.now(timezone.utc),
        "expires_at": _coerce_datetime(_row_get(row, "expires_at")) or datetime.now(timezone.utc),
        "accepted_at": _coerce_datetime(_row_get(row, "accepted_at")),
    }
    if include_token:
        return OrganizationInviteCreated(
            **base,
            token=_row_get(row, "token"),
            accept_url=f"/signup?invite_token={_row_get(row, 'token')}",
        )
    return OrganizationInvite(**base)


def _region_from_row(row: Any) -> Region:
    return Region(
        id=_row_get(row, "id"),
        org_id=_row_get(row, "org_id"),
        name=_row_get(row, "name"),
        description=_row_get(row, "description"),
        boundary=_row_get(row, "boundary"),
        created_at=_coerce_datetime(_row_get(row, "created_at")) or datetime.now(timezone.utc),
        updated_at=_coerce_datetime(_row_get(row, "updated_at")) or datetime.now(timezone.utc),
    )


def _sensor_from_row(row: Any) -> Sensor:
    return Sensor(
        id=_row_get(row, "id"),
        org_id=_row_get(row, "org_id"),
        name=_row_get(row, "name"),
        device_type=_row_get(row, "device_type"),
        region_id=_row_get(row, "region_id"),
        location=Coordinates(lat=float(_row_get(row, "lat")), lon=float(_row_get(row, "lon"))),
        status="online" if _row_get(row, "last_heard_at") else "registered",
        last_heard_at=_coerce_datetime(_row_get(row, "last_heard_at")),
    )


def _alert_from_row(row: Any) -> Alert:
    return Alert(
        id=_row_get(row, "id"),
        org_id=_row_get(row, "org_id"),
        type=AlertType(_row_get(row, "type")),
        sensor_id=_row_get(row, "sensor_id"),
        region_id=_row_get(row, "region_id"),
        location=Coordinates(lat=float(_row_get(row, "lat")), lon=float(_row_get(row, "lon"))),
        description=_row_get(row, "description"),
        priority=_row_get(row, "priority"),
        status=AlertStatus(_row_get(row, "status")),
        status_note=_row_get(row, "status_note"),
        classifier_label=_row_get(row, "classifier_label"),
        classifier_confidence=_row_get(row, "classifier_confidence"),
        classifier_model_version=_row_get(row, "classifier_model_version"),
        metadata=json.loads(_row_get(row, "metadata") or "{}") if isinstance(_row_get(row, "metadata"), str) else (_row_get(row, "metadata") or {}),
        created_at=_coerce_datetime(_row_get(row, "created_at")) or datetime.now(timezone.utc),
        updated_at=_coerce_datetime(_row_get(row, "updated_at")) or datetime.now(timezone.utc),
    )


def create_organization(payload: OrganizationCreate) -> Organization:
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                "INSERT INTO organizations (name, description) VALUES (?, ?)",
                (payload.name, payload.description),
            )
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (cursor.lastrowid,)).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO organizations (name, description)
                VALUES (%s, %s)
                RETURNING *
                """,
                (payload.name, payload.description),
            ).fetchone()
        return _organization_from_row(row)


def get_organization(org_id: int) -> Organization | None:
    with connection() as conn:
        if is_sqlite():
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM organizations WHERE id = %s", (org_id,)).fetchone()
        return _organization_from_row(row) if row else None


def list_organizations() -> list[Organization]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM organizations ORDER BY name, id").fetchall()
        return [_organization_from_row(row) for row in rows]




def create_invite(org_id: int, payload: OrganizationInviteCreate, *, invited_by_user_id: int, token: str) -> OrganizationInviteCreated:
    if payload.role != "member":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only member invites are supported")
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                """
                INSERT INTO organization_invites (org_id, email, role, token, status, invited_by_user_id, expires_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (org_id, payload.email.lower(), payload.role, token, invited_by_user_id, expires_at.isoformat()),
            )
            row = conn.execute("SELECT * FROM organization_invites WHERE id = ?", (cursor.lastrowid,)).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO organization_invites (org_id, email, role, token, status, invited_by_user_id, expires_at)
                VALUES (%s, %s, %s, %s, 'pending', %s, %s)
                RETURNING *
                """,
                (org_id, payload.email.lower(), payload.role, token, invited_by_user_id, expires_at),
            ).fetchone()
    return _invite_from_row(row, include_token=True)


def list_invites_for_org(org_id: int) -> list[OrganizationInvite]:
    with connection() as conn:
        placeholder = "?" if is_sqlite() else "%s"
        rows = conn.execute(
            f"SELECT * FROM organization_invites WHERE org_id = {placeholder} ORDER BY created_at DESC, id DESC",
            (org_id,),
        ).fetchall()
    return [_invite_from_row(row) for row in rows]


def get_invite_for_org(invite_id: int, org_id: int) -> OrganizationInvite | None:
    with connection() as conn:
        placeholder = "?" if is_sqlite() else "%s"
        row = conn.execute(
            f"SELECT * FROM organization_invites WHERE id = {placeholder} AND org_id = {placeholder}",
            (invite_id, org_id),
        ).fetchone()
    return _invite_from_row(row) if row else None


def get_invite_by_token(token: str) -> OrganizationInvite | None:
    with connection() as conn:
        placeholder = "?" if is_sqlite() else "%s"
        row = conn.execute(f"SELECT * FROM organization_invites WHERE token = {placeholder}", (token,)).fetchone()
    return _invite_from_row(row) if row else None


def revoke_invite(invite_id: int, org_id: int) -> OrganizationInvite | None:
    invite = get_invite_for_org(invite_id, org_id)
    if invite is None:
        return None
    if invite.status != InviteStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending invites can be revoked")
    with connection() as conn:
        if is_sqlite():
            conn.execute("UPDATE organization_invites SET status = 'revoked' WHERE id = ? AND org_id = ?", (invite_id, org_id))
            row = conn.execute("SELECT * FROM organization_invites WHERE id = ? AND org_id = ?", (invite_id, org_id)).fetchone()
        else:
            row = conn.execute(
                "UPDATE organization_invites SET status = 'revoked' WHERE id = %s AND org_id = %s RETURNING *",
                (invite_id, org_id),
            ).fetchone()
    return _invite_from_row(row) if row else None


def accept_invite(invite: OrganizationInvite) -> None:
    with connection() as conn:
        if is_sqlite():
            conn.execute(
                "UPDATE organization_invites SET status = 'accepted', accepted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (invite.id,),
            )
        else:
            conn.execute(
                "UPDATE organization_invites SET status = 'accepted', accepted_at = now() WHERE id = %s",
                (invite.id,),
            )


def create_user(name: str, email: str, password_hash: str, *, org_id: int | None, role: str = "member") -> dict[str, Any]:
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                "INSERT INTO users (organization_id, name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                (org_id, name, email.lower(), password_hash, role),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)

        row = conn.execute(
            """
            INSERT INTO users (organization_id, name, email, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (org_id, name, email.lower(), password_hash, role),
        ).fetchone()
        return dict(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with connection() as conn:
        if is_sqlite():
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        else:
            row = conn.execute("SELECT * FROM users WHERE email = %s", (email.lower(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with connection() as conn:
        if is_sqlite():
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
        return dict(row) if row else None


def create_region(org_id: int, payload: RegionCreate) -> Region:
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                "INSERT INTO regions (org_id, name, description, boundary_geojson) VALUES (?, ?, ?, ?)",
                (org_id, payload.name, payload.description, payload.boundary),
            )
            row = conn.execute(
                "SELECT id, org_id, name, description, boundary_geojson AS boundary, created_at, updated_at FROM regions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO regions (org_id, name, description, boundary)
                VALUES (%s, %s, %s, CASE WHEN %s IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) END)
                RETURNING id, org_id, name, description,
                          CASE WHEN boundary IS NULL THEN NULL ELSE ST_AsGeoJSON(boundary) END AS boundary,
                          created_at, updated_at
                """,
                (org_id, payload.name, payload.description, payload.boundary, payload.boundary),
            ).fetchone()
        return _region_from_row(row)


def list_regions_for_org(org_id: int) -> list[Region]:
    with connection() as conn:
        if is_sqlite():
            rows = conn.execute(
                "SELECT id, org_id, name, description, boundary_geojson AS boundary, created_at, updated_at FROM regions WHERE org_id = ? ORDER BY name, id",
                (org_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, org_id, name, description,
                       CASE WHEN boundary IS NULL THEN NULL ELSE ST_AsGeoJSON(boundary) END AS boundary,
                       created_at, updated_at
                FROM regions
                WHERE org_id = %s
                ORDER BY name, id
                """,
                (org_id,),
            ).fetchall()
        return [_region_from_row(row) for row in rows]


def get_region_for_org(region_id: int, org_id: int) -> Region | None:
    with connection() as conn:
        if is_sqlite():
            row = conn.execute(
                "SELECT id, org_id, name, description, boundary_geojson AS boundary, created_at, updated_at FROM regions WHERE id = ? AND org_id = ?",
                (region_id, org_id),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id, org_id, name, description,
                       CASE WHEN boundary IS NULL THEN NULL ELSE ST_AsGeoJSON(boundary) END AS boundary,
                       created_at, updated_at
                FROM regions
                WHERE id = %s AND org_id = %s
                """,
                (region_id, org_id),
            ).fetchone()
        return _region_from_row(row) if row else None


def _validate_region_for_org(region_id: int | None, org_id: int) -> None:
    if region_id is not None and get_region_for_org(region_id, org_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")


def list_sensors(org_id: int) -> list[Sensor]:
    with connection() as conn:
        if is_sqlite():
            rows = conn.execute(
                "SELECT id, org_id, name, device_type, region_id, lat, lon, last_heard_at FROM sensors WHERE org_id = ? ORDER BY id",
                (org_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, org_id, name, device_type, region_id, ST_Y(location) AS lat, ST_X(location) AS lon, last_heard_at
                FROM sensors
                WHERE org_id = %s
                ORDER BY id
                """,
                (org_id,),
            ).fetchall()
        return [_sensor_from_row(row) for row in rows]


def create_sensor(org_id: int, payload: SensorCreate) -> Sensor:
    _validate_region_for_org(payload.region_id, org_id)
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                """
                INSERT INTO sensors (org_id, name, device_type, region_id, lat, lon, last_heard_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (org_id, payload.name, payload.device_type, payload.region_id, payload.location.lat, payload.location.lon),
            )
            row = conn.execute(
                "SELECT id, org_id, name, device_type, region_id, lat, lon, last_heard_at FROM sensors WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO sensors (org_id, name, device_type, region_id, location, last_heard_at)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), now())
                RETURNING id, org_id, name, device_type, region_id, ST_Y(location) AS lat, ST_X(location) AS lon, last_heard_at
                """,
                (org_id, payload.name, payload.device_type, payload.region_id, payload.location.lon, payload.location.lat),
            ).fetchone()
        return _sensor_from_row(row)


def get_sensor(sensor_id: int, org_id: int | None = None) -> Sensor | None:
    with connection() as conn:
        if is_sqlite():
            sql = "SELECT id, org_id, name, device_type, region_id, lat, lon, last_heard_at FROM sensors WHERE id = ?"
            params: list[Any] = [sensor_id]
            if org_id is not None:
                sql += " AND org_id = ?"
                params.append(org_id)
            row = conn.execute(sql, params).fetchone()
        else:
            sql = """
                SELECT id, org_id, name, device_type, region_id, ST_Y(location) AS lat, ST_X(location) AS lon, last_heard_at
                FROM sensors
                WHERE id = %s
            """
            params = [sensor_id]
            if org_id is not None:
                sql += " AND org_id = %s"
                params.append(org_id)
            row = conn.execute(sql, params).fetchone()
        return _sensor_from_row(row) if row else None


def require_sensor(sensor_id: int, org_id: int | None = None) -> Sensor:
    sensor = get_sensor(sensor_id, org_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    return sensor


def _select_alerts_sql() -> str:
    if is_sqlite():
        return "SELECT * FROM alerts"
    return """
        SELECT id, org_id, sensor_id, region_id, type, ST_Y(location) AS lat, ST_X(location) AS lon,
               description, priority, status, status_note, classifier_label, classifier_confidence,
               classifier_model_version, metadata, created_at, updated_at
        FROM alerts
    """


def _alert_filter_clauses(
    *,
    org_id: int,
    status_filter: AlertStatus | None = None,
    alert_type: AlertType | None = None,
    sensor_id: int | None = None,
    region_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    bbox: AlertBBox | None = None,
) -> tuple[list[str], list[Any]]:
    placeholder = "?" if is_sqlite() else "%s"
    where = [f"org_id = {placeholder}"]
    params: list[Any] = [org_id]
    if status_filter is not None:
        where.append(f"status = {placeholder}")
        params.append(status_filter.value)
    if alert_type is not None:
        where.append(f"type = {placeholder}")
        params.append(alert_type.value)
    if sensor_id is not None:
        require_sensor(sensor_id, org_id)
        where.append(f"sensor_id = {placeholder}")
        params.append(sensor_id)
    if region_id is not None:
        _validate_region_for_org(region_id, org_id)
        where.append(f"region_id = {placeholder}")
        params.append(region_id)
    if start_time is not None:
        where.append(f"created_at >= {placeholder}")
        params.append(start_time.isoformat())
    if end_time is not None:
        where.append(f"created_at <= {placeholder}")
        params.append(end_time.isoformat())
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        if is_sqlite():
            where.extend([f"lon >= {placeholder}", f"lon <= {placeholder}", f"lat >= {placeholder}", f"lat <= {placeholder}"])
            params.extend([min_lon, max_lon, min_lat, max_lat])
        else:
            where.append(f"location && ST_MakeEnvelope({placeholder}, {placeholder}, {placeholder}, {placeholder}, 4326)")
            params.extend([min_lon, min_lat, max_lon, max_lat])
    return where, params


def list_alerts(
    *,
    org_id: int,
    status_filter: AlertStatus | None = None,
    alert_type: AlertType | None = None,
    sensor_id: int | None = None,
    region_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    bbox: AlertBBox | None = None,
) -> list[Alert]:
    where, params = _alert_filter_clauses(
        org_id=org_id,
        status_filter=status_filter,
        alert_type=alert_type,
        sensor_id=sensor_id,
        region_id=region_id,
        start_time=start_time,
        end_time=end_time,
        bbox=bbox,
    )
    sql = f"{_select_alerts_sql()} WHERE {' AND '.join(where)} ORDER BY created_at DESC, id DESC"
    with connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_alert_from_row(row) for row in rows]


def create_alert(org_id: int, payload: AlertCreate, *, status_value: AlertStatus = AlertStatus.open) -> Alert:
    if payload.sensor_id is not None:
        sensor = require_sensor(payload.sensor_id, org_id)
        if payload.region_id is None:
            payload.region_id = sensor.region_id
    _validate_region_for_org(payload.region_id, org_id)
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                """
                INSERT INTO alerts (
                    org_id, sensor_id, region_id, type, lat, lon, description, priority, status,
                    classifier_label, classifier_confidence, classifier_model_version, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    org_id,
                    payload.sensor_id,
                    payload.region_id,
                    payload.type.value,
                    payload.location.lat,
                    payload.location.lon,
                    payload.description,
                    payload.priority,
                    status_value.value,
                    payload.classifier_label,
                    payload.classifier_confidence,
                    payload.classifier_model_version,
                    json.dumps(payload.metadata or {}),
                ),
            )
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO alerts (
                    org_id, sensor_id, region_id, type, location, description, priority, status,
                    classifier_label, classifier_confidence, classifier_model_version, metadata
                )
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, org_id, sensor_id, region_id, type, ST_Y(location) AS lat, ST_X(location) AS lon,
                          description, priority, status, status_note, classifier_label, classifier_confidence,
                          classifier_model_version, metadata, created_at, updated_at
                """,
                (
                    org_id,
                    payload.sensor_id,
                    payload.region_id,
                    payload.type.value,
                    payload.location.lon,
                    payload.location.lat,
                    payload.description,
                    payload.priority,
                    status_value.value,
                    payload.classifier_label,
                    payload.classifier_confidence,
                    payload.classifier_model_version,
                    json.dumps(payload.metadata or {}),
                ),
            ).fetchone()
        return _alert_from_row(row)


def get_alert(alert_id: int, org_id: int | None = None) -> Alert | None:
    with connection() as conn:
        placeholder = "?" if is_sqlite() else "%s"
        sql = f"{_select_alerts_sql()} WHERE id = {placeholder}"
        params: list[Any] = [alert_id]
        if org_id is not None:
            sql += f" AND org_id = {placeholder}"
            params.append(org_id)
        row = conn.execute(sql, params).fetchone()
        return _alert_from_row(row) if row else None


def update_alert_status(alert_id: int, org_id: int, new_status: AlertStatus, note: str | None = None) -> Alert | None:
    with connection() as conn:
        if is_sqlite():
            conn.execute(
                """
                UPDATE alerts
                SET status = ?, status_note = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND org_id = ?
                """,
                (new_status.value, note, alert_id, org_id),
            )
            row = conn.execute("SELECT * FROM alerts WHERE id = ? AND org_id = ?", (alert_id, org_id)).fetchone()
        else:
            row = conn.execute(
                """
                UPDATE alerts
                SET status = %s, status_note = %s, updated_at = now()
                WHERE id = %s AND org_id = %s
                RETURNING id, org_id, sensor_id, region_id, type, ST_Y(location) AS lat, ST_X(location) AS lon,
                          description, priority, status, status_note, classifier_label, classifier_confidence,
                          classifier_model_version, metadata, created_at, updated_at
                """,
                (new_status.value, note, alert_id, org_id),
            ).fetchone()
        return _alert_from_row(row) if row else None




def _satellite_change_from_row(row: Any) -> SatelliteChangeResponse:
    metadata = _row_get(row, "metadata")
    return SatelliteChangeResponse(
        id=_row_get(row, "id"),
        org_id=_row_get(row, "org_id"),
        region_id=_row_get(row, "region_id"),
        source=SatelliteChangeSource(_row_get(row, "source")),
        change_type=SatelliteChangeType(_row_get(row, "change_type")),
        severity_score=float(_row_get(row, "severity_score")),
        confidence=float(_row_get(row, "confidence")),
        baseline_start=_coerce_datetime(_row_get(row, "baseline_start")),
        baseline_end=_coerce_datetime(_row_get(row, "baseline_end")),
        observation_start=_coerce_datetime(_row_get(row, "observation_start")),
        observation_end=_coerce_datetime(_row_get(row, "observation_end")),
        description=_row_get(row, "description"),
        latitude=_row_get(row, "latitude"),
        longitude=_row_get(row, "longitude"),
        geometry=_row_get(row, "geometry"),
        metadata=json.loads(metadata or "{}") if isinstance(metadata, str) else (metadata or {}),
        created_at=_coerce_datetime(_row_get(row, "created_at")) or datetime.now(timezone.utc),
        updated_at=_coerce_datetime(_row_get(row, "updated_at")) or datetime.now(timezone.utc),
    )


def create_satellite_change(org_id: int, payload: SatelliteChangeCreate) -> SatelliteChangeResponse:
    _validate_region_for_org(payload.region_id, org_id)
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                """
                INSERT INTO satellite_change_events (
                    org_id, region_id, source, change_type, severity_score, confidence,
                    baseline_start, baseline_end, observation_start, observation_end,
                    description, latitude, longitude, geometry_geojson, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    org_id, payload.region_id, payload.source.value, payload.change_type.value,
                    payload.severity_score, payload.confidence,
                    payload.baseline_start.isoformat() if payload.baseline_start else None,
                    payload.baseline_end.isoformat() if payload.baseline_end else None,
                    payload.observation_start.isoformat() if payload.observation_start else None,
                    payload.observation_end.isoformat() if payload.observation_end else None,
                    payload.description, payload.latitude, payload.longitude, payload.geometry,
                    json.dumps(payload.metadata or {}),
                ),
            )
            row = conn.execute(
                "SELECT id, org_id, region_id, source, change_type, severity_score, confidence, baseline_start, baseline_end, observation_start, observation_end, description, latitude, longitude, geometry_geojson AS geometry, metadata, created_at, updated_at FROM satellite_change_events WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO satellite_change_events (
                    org_id, region_id, source, change_type, severity_score, confidence,
                    baseline_start, baseline_end, observation_start, observation_end,
                    description, latitude, longitude, geometry, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) END, %s)
                RETURNING id, org_id, region_id, source, change_type, severity_score, confidence,
                          baseline_start, baseline_end, observation_start, observation_end,
                          description, latitude, longitude,
                          CASE WHEN geometry IS NULL THEN NULL ELSE ST_AsGeoJSON(geometry) END AS geometry,
                          metadata, created_at, updated_at
                """,
                (
                    org_id, payload.region_id, payload.source.value, payload.change_type.value,
                    payload.severity_score, payload.confidence, payload.baseline_start, payload.baseline_end,
                    payload.observation_start, payload.observation_end, payload.description,
                    payload.latitude, payload.longitude, payload.geometry, payload.geometry,
                    json.dumps(payload.metadata or {}),
                ),
            ).fetchone()
        return _satellite_change_from_row(row)


def list_satellite_changes(org_id: int, region_id: int | None = None) -> list[SatelliteChangeResponse]:
    if region_id is not None:
        _validate_region_for_org(region_id, org_id)
    with connection() as conn:
        placeholder = "?" if is_sqlite() else "%s"
        if is_sqlite():
            sql = "SELECT id, org_id, region_id, source, change_type, severity_score, confidence, baseline_start, baseline_end, observation_start, observation_end, description, latitude, longitude, geometry_geojson AS geometry, metadata, created_at, updated_at FROM satellite_change_events WHERE org_id = ?"
        else:
            sql = """
                SELECT id, org_id, region_id, source, change_type, severity_score, confidence,
                       baseline_start, baseline_end, observation_start, observation_end,
                       description, latitude, longitude,
                       CASE WHEN geometry IS NULL THEN NULL ELSE ST_AsGeoJSON(geometry) END AS geometry,
                       metadata, created_at, updated_at
                FROM satellite_change_events WHERE org_id = %s
            """
        params: list[Any] = [org_id]
        if region_id is not None:
            sql += f" AND region_id = {placeholder}"
            params.append(region_id)
        sql += " ORDER BY created_at DESC, id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [_satellite_change_from_row(row) for row in rows]


def get_satellite_change(change_id: int, org_id: int) -> SatelliteChangeResponse | None:
    return next((change for change in list_satellite_changes(org_id) if change.id == change_id), None)


def delete_satellite_change(change_id: int, org_id: int) -> bool:
    with connection() as conn:
        placeholder = "?" if is_sqlite() else "%s"
        cursor = conn.execute(f"DELETE FROM satellite_change_events WHERE id = {placeholder} AND org_id = {placeholder}", (change_id, org_id))
        return cursor.rowcount > 0


def fused_alert_exists(org_id: int, acoustic_alert_id: int, satellite_change_id: int) -> bool:
    return any(
        alert.type == AlertType.fusion
        and alert.metadata
        and alert.metadata.get("acoustic_alert_id") == acoustic_alert_id
        and alert.metadata.get("satellite_change_id") == satellite_change_id
        for alert in list_alerts(org_id=org_id, alert_type=AlertType.fusion)
    )


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def create_audio_clip(file_path: Path, *, org_id: int, sensor_id: int) -> int:
    require_sensor(sensor_id, org_id)
    with connection() as conn:
        if is_sqlite():
            cursor = conn.execute(
                "INSERT INTO audio_clips (org_id, sensor_id, file_url) VALUES (?, ?, ?)",
                (org_id, sensor_id, str(file_path)),
            )
            return int(cursor.lastrowid)

        row = conn.execute(
            """
            INSERT INTO audio_clips (org_id, sensor_id, captured_at, file_url)
            VALUES (%s, %s, now(), %s)
            RETURNING id
            """,
            (org_id, sensor_id, str(file_path)),
        ).fetchone()
        return int(row["id"])
