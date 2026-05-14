from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class Coordinates(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class HealthResponse(BaseModel):
    status: str
    service: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(LoginRequest):
    name: str
    organization_name: str | None = None
    invite_token: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganizationCreate(BaseModel):
    name: str
    description: str | None = None


class Organization(OrganizationCreate):
    id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))




class InviteStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"
    expired = "expired"


class OrganizationInviteCreate(BaseModel):
    email: str
    role: str = "member"


class OrganizationInvite(BaseModel):
    id: int
    org_id: int
    email: str
    role: str
    status: InviteStatus
    invited_by_user_id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    accepted_at: datetime | None = None


class OrganizationInviteCreated(OrganizationInvite):
    token: str
    accept_url: str


class UserProfile(BaseModel):
    id: int
    name: str
    email: str
    role: str
    org_id: int | None = None
    organization: Organization | None = None


class RegionCreate(BaseModel):
    name: str
    description: str | None = None
    boundary: str | None = None


class Region(RegionCreate):
    id: int
    org_id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SensorCreate(BaseModel):
    name: str
    device_type: str = "forest-listening-unit"
    location: Coordinates
    region_id: int | None = None


class Sensor(SensorCreate):
    id: int
    org_id: int | None = None
    status: str = "online"
    last_heard_at: datetime | None = None


class AlertType(str, Enum):
    audio = "audio"
    satellite = "satellite"
    fusion = "fusion"
    fused_logging_risk = "fused_logging_risk"


class AlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    investigating = "investigating"
    resolved = "resolved"
    dismissed = "dismissed"


class AlertCreate(BaseModel):
    type: AlertType
    location: Coordinates
    description: str
    priority: str = "medium"
    sensor_id: int | None = None
    region_id: int | None = None
    classifier_label: str | None = None
    classifier_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    classifier_model_version: str | None = None
    metadata: dict[str, Any] | None = None


class AlertStatusUpdate(BaseModel):
    status: AlertStatus
    note: str | None = Field(default=None, max_length=500)


class Alert(AlertCreate):
    id: int
    org_id: int | None = None
    status: AlertStatus = AlertStatus.open
    status_note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SatelliteChangeSource(str, Enum):
    manual = "manual"
    sentinel_stub = "sentinel_stub"
    landsat_stub = "landsat_stub"
    ndvi_stub = "ndvi_stub"
    csv_ndvi = "csv_ndvi"


class SatelliteChangeType(str, Enum):
    ndvi_drop = "ndvi_drop"
    canopy_loss = "canopy_loss"
    vegetation_stress = "vegetation_stress"
    burn_scar = "burn_scar"
    unknown = "unknown"


class SatelliteChangeCreate(BaseModel):
    region_id: int | None = None
    source: SatelliteChangeSource = SatelliteChangeSource.manual
    change_type: SatelliteChangeType = SatelliteChangeType.unknown
    severity_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    baseline_start: datetime | None = None
    baseline_end: datetime | None = None
    observation_start: datetime | None = None
    observation_end: datetime | None = None
    description: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geometry: str | None = None
    metadata: dict[str, Any] | None = None


class SatelliteChangeResponse(SatelliteChangeCreate):
    id: int
    org_id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NdviIngestionStatus(str, Enum):
    pending = "pending"
    processed = "processed"
    failed = "failed"


class NdviSourceType(str, Enum):
    csv = "csv"
    geojson = "geojson"
    json = "json"


class NdviIngestionBatch(BaseModel):
    id: int
    org_id: int
    region_id: int | None = None
    uploaded_by_user_id: int
    source_type: NdviSourceType
    filename: str | None = None
    status: NdviIngestionStatus
    row_count: int = 0
    created_change_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None


class NdviUploadResponse(BaseModel):
    batch_id: int
    status: NdviIngestionStatus
    row_count: int
    created_change_count: int
    created_satellite_change_ids: list[int]
    skipped_count: int


class FusionRunRequest(BaseModel):
    region_id: int | None = None
    time_window_days: int = Field(default=14, ge=1, le=365)
    distance_meters: float = Field(default=500, gt=0)
    min_acoustic_confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    min_satellite_severity: float = Field(default=0.3, ge=0.0, le=1.0)


class FusionRunResponse(BaseModel):
    created_count: int
    matched_count: int
    alerts: list[Alert]


class ClipUploadResponse(BaseModel):
    clip_id: int
    filename: str
    sensor_id: int | None = None
    classifier_label: str
    classifier_confidence: float
    classifier_model_version: str
    generated_alert: Alert | None = None
