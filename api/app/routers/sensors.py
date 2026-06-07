from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import create_sensor as persist_sensor
from app.repositories import list_sensors as load_sensors
from app.repositories import update_sensor_heartbeat
from app.schemas import HeartbeatResponse, Sensor, SensorCreate
from app.security import get_current_user, org_id_for_user, require_admin

router = APIRouter()


@router.get("", response_model=list[Sensor])
def list_sensors(current_user: dict = Depends(get_current_user)) -> list[Sensor]:
    return load_sensors(org_id_for_user(current_user))


@router.post("", response_model=Sensor, status_code=status.HTTP_201_CREATED)
def create_sensor(payload: SensorCreate, current_user: dict = Depends(require_admin)) -> Sensor:
    return persist_sensor(org_id_for_user(current_user), payload)


@router.post("/{sensor_id}/heartbeat", response_model=HeartbeatResponse)
def sensor_heartbeat(
    sensor_id: int,
    current_user: dict = Depends(get_current_user),
) -> HeartbeatResponse:
    sensor = update_sensor_heartbeat(sensor_id, org_id_for_user(current_user))
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    return HeartbeatResponse(
        sensor_id=sensor.id,
        last_heard_at=sensor.last_heard_at,
        status=sensor.status,
    )
