from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.repositories import create_alert, create_audio_clip, require_sensor
from app.schemas import AlertCreate, AlertType, ClipUploadResponse
from app.security import get_current_user, org_id_for_user
from app.services.audio_classifier import classify_clip

router = APIRouter()

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}


@router.post("/upload", response_model=ClipUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_clip(
    file: UploadFile = File(...),
    sensor_id: int | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
) -> ClipUploadResponse:
    if sensor_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sensor_id is required")
    org_id = org_id_for_user(current_user)
    sensor = require_sensor(sensor_id, org_id)

    original_name = Path(file.filename or "")
    if original_name.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported audio file extension")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file is empty")

    settings = get_settings()
    storage_path = Path(settings.audio_storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid4().hex}-{original_name.name}"
    destination = storage_path / safe_name
    destination.write_bytes(contents)

    classifier_result = classify_clip(destination)
    clip_id = create_audio_clip(destination, org_id=org_id, sensor_id=sensor_id)
    generated_alert = create_alert(
        org_id,
        AlertCreate(
            type=AlertType.audio,
            sensor_id=sensor_id,
            region_id=sensor.region_id,
            location=sensor.location,
            description=(
                f"Audio classifier detected '{classifier_result.label}' "
                f"with {classifier_result.confidence:.0%} confidence."
            ),
            priority="high" if classifier_result.label in {"chainsaw", "gunshot"} else "medium",
            classifier_label=classifier_result.label,
            classifier_confidence=classifier_result.confidence,
            classifier_model_version=classifier_result.model_version,
        ),
    )

    return ClipUploadResponse(
        clip_id=clip_id,
        filename=file.filename or safe_name,
        sensor_id=sensor_id,
        classifier_label=classifier_result.label,
        classifier_confidence=classifier_result.confidence,
        classifier_model_version=classifier_result.model_version,
        generated_alert=generated_alert,
    )
