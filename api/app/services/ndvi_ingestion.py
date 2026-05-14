from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

from app.repositories import create_ndvi_ingestion_batch, create_satellite_change, update_ndvi_ingestion_batch
from app.schemas import (
    NdviIngestionStatus,
    NdviSourceType,
    NdviUploadResponse,
    SatelliteChangeCreate,
    SatelliteChangeSource,
    SatelliteChangeType,
)

REQUIRED_NDVI_COLUMNS = {"latitude", "longitude", "baseline_ndvi", "recent_ndvi"}
DEFAULT_LOSS_THRESHOLD = -0.15
DEFAULT_CONFIDENCE = 0.75


def _optional_text(row: dict[str, str], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_datetime(row: dict[str, str], key: str) -> datetime | None:
    value = _optional_text(row, key)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO-8601 datetime") from exc


def _parse_float(row: dict[str, str], key: str, *, row_number: int) -> float:
    value = _optional_text(row, key)
    if value is None:
        raise ValueError(f"Row {row_number}: {key} is required")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: {key} must be a number") from exc


def parse_ndvi_csv(file_bytes: bytes | str | Path) -> list[dict[str, str]]:
    if isinstance(file_bytes, Path):
        text = file_bytes.read_text(encoding="utf-8-sig")
    else:
        text = file_bytes.decode("utf-8-sig") if isinstance(file_bytes, bytes) else file_bytes
    reader = csv.DictReader(StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_NDVI_COLUMNS - fieldnames)
    if missing:
        raise ValueError(f"Missing required NDVI CSV columns: {', '.join(missing)}")
    return [dict(row) for row in reader]


def validate_ndvi_row(row: dict[str, str], *, row_number: int, default_confidence: float = DEFAULT_CONFIDENCE) -> dict[str, Any]:
    latitude = _parse_float(row, "latitude", row_number=row_number)
    longitude = _parse_float(row, "longitude", row_number=row_number)
    baseline_ndvi = _parse_float(row, "baseline_ndvi", row_number=row_number)
    recent_ndvi = _parse_float(row, "recent_ndvi", row_number=row_number)

    if not -90 <= latitude <= 90:
        raise ValueError(f"Row {row_number}: latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError(f"Row {row_number}: longitude must be between -180 and 180")
    if not -1 <= baseline_ndvi <= 1:
        raise ValueError(f"Row {row_number}: baseline_ndvi must be between -1 and 1")
    if not -1 <= recent_ndvi <= 1:
        raise ValueError(f"Row {row_number}: recent_ndvi must be between -1 and 1")
    if not 0 <= default_confidence <= 1:
        raise ValueError("default_confidence must be between 0 and 1")

    confidence_value = _optional_text(row, "confidence")
    try:
        confidence = default_confidence if confidence_value is None else float(confidence_value)
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: confidence must be a number") from exc
    if not 0 <= confidence <= 1:
        raise ValueError(f"Row {row_number}: confidence must be between 0 and 1")

    region_value = _optional_text(row, "region_id")
    try:
        region_id = int(region_value) if region_value is not None else None
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: region_id must be an integer") from exc

    ndvi_delta = recent_ndvi - baseline_ndvi
    severity_score = min(abs(ndvi_delta) / 0.5, 1.0) if ndvi_delta < 0 else 0.0
    return {
        "row_number": row_number,
        "latitude": latitude,
        "longitude": longitude,
        "baseline_ndvi": baseline_ndvi,
        "recent_ndvi": recent_ndvi,
        "ndvi_delta": ndvi_delta,
        "severity_score": severity_score,
        "confidence": confidence,
        "region_id": region_id,
        "baseline_start": _optional_datetime(row, "baseline_start"),
        "baseline_end": _optional_datetime(row, "baseline_end"),
        "observation_start": _optional_datetime(row, "observation_start"),
        "observation_end": _optional_datetime(row, "observation_end"),
        "description": _optional_text(row, "description"),
    }


def ndvi_row_to_satellite_change(
    row: dict[str, Any],
    *,
    org_id: int,
    region_id: int | None,
    ingestion_batch_id: int,
    loss_threshold: float = DEFAULT_LOSS_THRESHOLD,
) -> SatelliteChangeCreate:
    del org_id  # org scoping is applied by repository create_satellite_change.
    effective_region_id = row["region_id"] if row.get("region_id") is not None else region_id
    description = row.get("description") or (
        "NDVI drop detected from CSV ingestion: "
        f"baseline {row['baseline_ndvi']:.3f}, recent {row['recent_ndvi']:.3f}, delta {row['ndvi_delta']:.3f}."
    )
    return SatelliteChangeCreate(
        region_id=effective_region_id,
        source=SatelliteChangeSource.csv_ndvi,
        change_type=SatelliteChangeType.ndvi_drop,
        severity_score=row["severity_score"],
        confidence=row["confidence"],
        baseline_start=row.get("baseline_start"),
        baseline_end=row.get("baseline_end"),
        observation_start=row.get("observation_start"),
        observation_end=row.get("observation_end"),
        description=description,
        latitude=row["latitude"],
        longitude=row["longitude"],
        metadata={
            "baseline_ndvi": row["baseline_ndvi"],
            "recent_ndvi": row["recent_ndvi"],
            "ndvi_delta": row["ndvi_delta"],
            "loss_threshold": loss_threshold,
            "ingestion_batch_id": ingestion_batch_id,
            "row_number": row["row_number"],
        },
    )


def process_ndvi_csv_upload(
    *,
    org_id: int,
    uploaded_by_user_id: int,
    file_bytes: bytes,
    filename: str | None = None,
    region_id: int | None = None,
    loss_threshold: float = DEFAULT_LOSS_THRESHOLD,
    default_confidence: float = DEFAULT_CONFIDENCE,
) -> NdviUploadResponse:
    batch = create_ndvi_ingestion_batch(
        org_id=org_id,
        uploaded_by_user_id=uploaded_by_user_id,
        region_id=region_id,
        source_type=NdviSourceType.csv,
        filename=filename,
        metadata={"loss_threshold": loss_threshold, "default_confidence": default_confidence},
    )
    created_ids: list[int] = []
    rows: list[dict[str, str]] = []
    try:
        if loss_threshold >= 0:
            raise ValueError("loss_threshold must be negative")
        if not 0 <= default_confidence <= 1:
            raise ValueError("default_confidence must be between 0 and 1")
        rows = parse_ndvi_csv(file_bytes)
        validated_rows = [validate_ndvi_row(raw_row, row_number=index, default_confidence=default_confidence) for index, raw_row in enumerate(rows, start=2)]
        for row in validated_rows:
            if row["ndvi_delta"] > loss_threshold:
                continue
            change = create_satellite_change(
                org_id,
                ndvi_row_to_satellite_change(
                    row,
                    org_id=org_id,
                    region_id=region_id,
                    ingestion_batch_id=batch.id,
                    loss_threshold=loss_threshold,
                ),
            )
            created_ids.append(change.id)
        update_ndvi_ingestion_batch(
            batch.id,
            org_id,
            status_value=NdviIngestionStatus.processed,
            row_count=len(rows),
            created_change_count=len(created_ids),
            metadata={"loss_threshold": loss_threshold, "default_confidence": default_confidence, "created_satellite_change_ids": created_ids},
        )
        return NdviUploadResponse(
            batch_id=batch.id,
            status=NdviIngestionStatus.processed,
            row_count=len(rows),
            created_change_count=len(created_ids),
            created_satellite_change_ids=created_ids,
            skipped_count=len(rows) - len(created_ids),
        )
    except Exception as exc:
        update_ndvi_ingestion_batch(
            batch.id,
            org_id,
            status_value=NdviIngestionStatus.failed,
            row_count=len(rows),
            created_change_count=len(created_ids),
            error_message=str(exc),
            metadata={"loss_threshold": loss_threshold, "default_confidence": default_confidence, "created_satellite_change_ids": created_ids},
        )
        raise
