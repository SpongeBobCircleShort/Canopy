from fastapi import APIRouter, Depends

from app.schemas import FusionRunRequest, FusionRunResponse
from app.security import org_id_for_user, require_admin
from app.services.fusion import run_fusion

router = APIRouter()


@router.post("/run", response_model=FusionRunResponse)
def run_fusion_route(payload: FusionRunRequest, current_user: dict = Depends(require_admin)) -> FusionRunResponse:
    return run_fusion(org_id_for_user(current_user), payload)
