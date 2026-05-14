from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.repositories import get_ndvi_ingestion_batch, list_ndvi_ingestion_batches
from app.schemas import NdviIngestionBatch, NdviUploadResponse
from app.security import get_current_user, org_id_for_user, require_admin
from app.services.ndvi_ingestion import DEFAULT_CONFIDENCE, DEFAULT_LOSS_THRESHOLD, process_ndvi_csv_upload

router = APIRouter()


@router.post("/upload-csv", response_model=NdviUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_ndvi_csv(
    file: UploadFile = File(...),
    region_id: int | None = Form(default=None),
    loss_threshold: float = Form(default=DEFAULT_LOSS_THRESHOLD),
    default_confidence: float = Form(default=DEFAULT_CONFIDENCE),
    current_user: dict = Depends(require_admin),
) -> NdviUploadResponse:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="NDVI upload must be a CSV file")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded NDVI CSV is empty")
    try:
        return process_ndvi_csv_upload(
            org_id=org_id_for_user(current_user),
            uploaded_by_user_id=current_user["id"],
            file_bytes=contents,
            filename=file.filename,
            region_id=region_id,
            loss_threshold=loss_threshold,
            default_confidence=default_confidence,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/batches", response_model=list[NdviIngestionBatch])
def list_batches(current_user: dict = Depends(get_current_user)) -> list[NdviIngestionBatch]:
    return list_ndvi_ingestion_batches(org_id_for_user(current_user))


@router.get("/batches/{batch_id}", response_model=NdviIngestionBatch)
def get_batch(batch_id: int, current_user: dict = Depends(get_current_user)) -> NdviIngestionBatch:
    batch = get_ndvi_ingestion_batch(batch_id, org_id_for_user(current_user))
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NDVI ingestion batch not found")
    return batch
