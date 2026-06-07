from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import create_satellite_change, delete_satellite_change, get_satellite_change, list_satellite_changes
from app.schemas import SatelliteChangeCreate, SatelliteChangeResponse, SentinelIngestRequest, SentinelIngestResponse
from app.security import get_current_user, org_id_for_user, require_admin
from app.services.sentinel_ingestion import run_sentinel_ingest

router = APIRouter()


@router.get("", response_model=list[SatelliteChangeResponse])
def list_changes(region_id: int | None = None, current_user: dict = Depends(get_current_user)) -> list[SatelliteChangeResponse]:
    return list_satellite_changes(org_id_for_user(current_user), region_id=region_id)


@router.post("", response_model=SatelliteChangeResponse, status_code=status.HTTP_201_CREATED)
def create_change(payload: SatelliteChangeCreate, current_user: dict = Depends(require_admin)) -> SatelliteChangeResponse:
    return create_satellite_change(org_id_for_user(current_user), payload)


@router.post("/ingest-sentinel", response_model=SentinelIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_sentinel(
    payload: SentinelIngestRequest,
    current_user: dict = Depends(require_admin),
) -> SentinelIngestResponse:
    """
    Trigger a Sentinel-2 NDVI ingestion run for the authenticated organisation.

    Queries the Copernicus STAC API for scenes in the baseline and observation
    windows, computes NDVI deltas across a configurable grid, and persists
    satellite change events for cells that exceed the loss threshold.
    """
    return run_sentinel_ingest(
        payload,
        org_id=org_id_for_user(current_user),
        create_satellite_change_fn=create_satellite_change,
    )


@router.get("/{change_id}", response_model=SatelliteChangeResponse)
def get_change(change_id: int, current_user: dict = Depends(get_current_user)) -> SatelliteChangeResponse:
    change = get_satellite_change(change_id, org_id_for_user(current_user))
    if change is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Satellite change not found")
    return change


@router.delete("/{change_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_change(change_id: int, current_user: dict = Depends(require_admin)) -> None:
    if not delete_satellite_change(change_id, org_id_for_user(current_user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Satellite change not found")
