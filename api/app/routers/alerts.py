import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.repositories import create_alert as persist_alert
from app.repositories import get_alert as load_alert
from app.repositories import list_alerts as load_alerts
from app.repositories import update_alert_status as persist_alert_status
from app.schemas import Alert, AlertCreate, AlertStatus, AlertStatusUpdate, AlertType
from app.security import get_current_user, org_id_for_user, require_admin

router = APIRouter()


def _parse_bbox(raw_bbox: str | None) -> tuple[float, float, float, float] | None:
    if raw_bbox is None:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = [float(part.strip()) for part in raw_bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bbox must be min_lon,min_lat,max_lon,max_lat",
        ) from exc
    if min_lon > max_lon or min_lat > max_lat:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bbox minimums must be <= maximums")
    return min_lon, min_lat, max_lon, max_lat


def _filtered_alerts(
    org_id: int,
    status_value: AlertStatus | None = Query(default=None, alias="status"),
    type_value: AlertType | None = Query(default=None, alias="type"),
    sensor_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    bbox: str | None = None,
) -> list[Alert]:
    return load_alerts(
        org_id=org_id,
        status_filter=status_value,
        alert_type=type_value,
        sensor_id=sensor_id,
        start_time=start_time,
        end_time=end_time,
        bbox=_parse_bbox(bbox),
    )


@router.get("", response_model=list[Alert])
def list_alerts(
    status_value: AlertStatus | None = Query(default=None, alias="status"),
    type_value: AlertType | None = Query(default=None, alias="type"),
    sensor_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    bbox: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> list[Alert]:
    return _filtered_alerts(org_id_for_user(current_user), status_value, type_value, sensor_id, start_time, end_time, bbox)


@router.post("", response_model=Alert, status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertCreate, current_user: dict = Depends(require_admin)) -> Alert:
    return persist_alert(org_id_for_user(current_user), payload)


@router.get("/export", response_class=Response)
def export_alerts(
    format: str = "csv",
    status_value: AlertStatus | None = Query(default=None, alias="status"),
    type_value: AlertType | None = Query(default=None, alias="type"),
    sensor_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    bbox: str | None = None,
    current_user: dict = Depends(require_admin),
) -> Response:
    if format != "csv":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only csv export is supported")
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "type", "status", "priority", "description", "latitude", "longitude", "sensor_id", "created_at"])
    for alert in _filtered_alerts(org_id_for_user(current_user), status_value, type_value, sensor_id, start_time, end_time, bbox):
        writer.writerow(
            [
                alert.id,
                alert.type.value,
                alert.status.value,
                alert.priority,
                alert.description,
                alert.location.lat,
                alert.location.lon,
                alert.sensor_id,
                alert.created_at.isoformat(),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="canopy-alerts.csv"'},
    )


@router.get("/export.csv", response_class=Response)
def export_alerts_csv(
    status_value: AlertStatus | None = Query(default=None, alias="status"),
    type_value: AlertType | None = Query(default=None, alias="type"),
    sensor_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    bbox: str | None = None,
    current_user: dict = Depends(require_admin),
) -> Response:
    return export_alerts("csv", status_value, type_value, sensor_id, start_time, end_time, bbox, current_user)


@router.patch("/{alert_id}/status", response_model=Alert)
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    current_user: dict = Depends(require_admin),
) -> Alert:
    alert = persist_alert_status(alert_id, org_id_for_user(current_user), payload.status, payload.note)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.get("/{alert_id}", response_model=Alert)
def get_alert(alert_id: int, current_user: dict = Depends(get_current_user)) -> Alert:
    alert = load_alert(alert_id, org_id_for_user(current_user))
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert
