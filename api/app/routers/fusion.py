from typing import Any

from fastapi import APIRouter, Depends

from app.schemas import FusionRunRequest, FusionRunResponse
from app.security import get_current_user, org_id_for_user, require_admin
from app.services.fusion import run_fusion
from app.services.scheduler import get_schedule_status

router = APIRouter()


@router.post("/run", response_model=FusionRunResponse)
def run_fusion_route(payload: FusionRunRequest, current_user: dict = Depends(require_admin)) -> FusionRunResponse:
    return run_fusion(org_id_for_user(current_user), payload)


@router.get("/schedule", response_model=dict[str, Any])
def fusion_schedule_status(_current_user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return get_schedule_status()
