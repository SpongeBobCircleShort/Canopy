from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import create_region, get_region_for_org, list_regions_for_org
from app.schemas import Region, RegionCreate
from app.security import get_current_user, org_id_for_user, require_admin

router = APIRouter()


@router.get("", response_model=list[Region])
def list_regions(current_user: dict = Depends(get_current_user)) -> list[Region]:
    return list_regions_for_org(org_id_for_user(current_user))


@router.post("", response_model=Region, status_code=status.HTTP_201_CREATED)
def create_region_route(payload: RegionCreate, current_user: dict = Depends(require_admin)) -> Region:
    return create_region(org_id_for_user(current_user), payload)


@router.get("/{region_id}", response_model=Region)
def get_region(region_id: int, current_user: dict = Depends(get_current_user)) -> Region:
    region = get_region_for_org(region_id, org_id_for_user(current_user))
    if region is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    return region
