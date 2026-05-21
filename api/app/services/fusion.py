from datetime import datetime, timedelta, timezone

from app.repositories import create_alert, distance_meters, fused_alert_exists, list_alerts, list_satellite_changes
from app.schemas import Alert, AlertCreate, AlertType, FusionRunRequest, FusionRunResponse

FUSION_RULE_VERSION = "rule-fusion-v0"


def _priority(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _within_window(alert_time: datetime, change, days: int) -> bool:
    window = timedelta(days=days)
    start = change.observation_start or change.created_at
    end = change.observation_end or change.created_at
    return (start - window) <= alert_time <= (end + window)


def run_fusion(org_id: int, request: FusionRunRequest) -> FusionRunResponse:
    acoustic_alerts = [
        alert
        for alert in list_alerts(org_id=org_id, alert_type=AlertType.audio, region_id=request.region_id)
        if (alert.classifier_confidence or 0.0) >= request.min_acoustic_confidence
    ]
    satellite_changes = [
        change
        for change in list_satellite_changes(org_id, region_id=request.region_id)
        if change.severity_score >= request.min_satellite_severity and change.latitude is not None and change.longitude is not None
    ]
    matched_count = 0
    created: list[Alert] = []
    now = datetime.now(timezone.utc)

    for alert in acoustic_alerts:
        nearby_changes = []
        for change in satellite_changes:
            if change.region_id is not None and alert.region_id is not None and change.region_id != alert.region_id:
                continue
            if not _within_window(alert.created_at, change, request.time_window_days):
                continue
            distance = distance_meters(alert.location.lat, alert.location.lon, float(change.latitude), float(change.longitude))
            if distance <= request.distance_meters:
                nearby_changes.append((change, distance))

        if not nearby_changes:
            continue

        # Find the single closest satellite change to avoid duplicate fusion alerts
        best_change, best_distance = min(nearby_changes, key=lambda x: x[1])

        matched_count += 1
        if fused_alert_exists(org_id, alert.id, best_change.id):
            continue

        recurrence_bonus = 0.1 if len(nearby_changes) > 1 else 0.0
        acoustic_confidence = alert.classifier_confidence or 0.0
        fusion_score = (
            0.45 * acoustic_confidence
            + 0.35 * best_change.severity_score
            + 0.10 * best_change.confidence
            + 0.10 * recurrence_bonus
        )
        metadata = {
            "acoustic_alert_id": alert.id,
            "satellite_change_id": best_change.id,
            "acoustic_confidence": acoustic_confidence,
            "satellite_severity_score": best_change.severity_score,
            "satellite_confidence": best_change.confidence,
            "distance_meters": round(best_distance, 2),
            "fusion_score": round(fusion_score, 4),
            "fusion_rule_version": FUSION_RULE_VERSION,
            "created_at": now.isoformat(),
        }
        for key in ("baseline_ndvi", "recent_ndvi", "ndvi_delta", "ingestion_batch_id", "loss_threshold", "row_number"):
            if best_change.metadata and key in best_change.metadata:
                metadata[key] = best_change.metadata[key]
        created.append(
            create_alert(
                org_id,
                AlertCreate(
                    type=AlertType.fusion,
                    sensor_id=alert.sensor_id,
                    region_id=alert.region_id or best_change.region_id,
                    location=alert.location,
                    description=(
                        f"Fusion alert: acoustic evidence '{alert.classifier_label or 'audio'}' "
                        f"matched satellite change '{best_change.change_type.value}' within {round(best_distance)}m."
                    ),
                    priority=_priority(fusion_score),
                    classifier_label=alert.classifier_label,
                    classifier_confidence=alert.classifier_confidence,
                    classifier_model_version=alert.classifier_model_version,
                    metadata=metadata,
                ),
            )
        )
    return FusionRunResponse(created_count=len(created), matched_count=matched_count, alerts=created)
