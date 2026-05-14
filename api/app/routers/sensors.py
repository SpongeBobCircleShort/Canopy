from fastapi import APIRouter, Depends, status

from app.repositories import create_sensor as persist_sensor
from app.repositories import list_sensors as load_sensors
from app.schemas import Sensor, SensorCreate
from app.security import get_current_user, org_id_for_user, require_admin

router = APIRouter()


@router.get("", response_model=list[Sensor])
def list_sensors(current_user: dict = Depends(get_current_user)) -> list[Sensor]:
    return load_sensors(org_id_for_user(current_user))


@router.post("", response_model=Sensor, status_code=status.HTTP_201_CREATED)
def create_sensor(payload: SensorCreate, current_user: dict = Depends(require_admin)) -> Sensor:
    return persist_sensor(org_id_for_user(current_user), payload)
