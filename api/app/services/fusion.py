"""Spatiotemporal Decaying Fusion Engine — rule-fusion-v2.

Improvements over v1:
  • Temporal decay: acoustic and satellite evidence is down-weighted
    exponentially as the time gap between observation and alert grows.
    Weight = 2^(-Δt / halflife).
  • Spatial decay: Gaussian proximity weighting replaces the binary
    distance threshold.  Weight = exp(-(d/sigma)^2 / 2).
  • Multi-signal compounding: when N satellite changes independently
    corroborate an acoustic alert, their signals compound with
    diminishing returns via: 1 - product(1 - p_i).
  • Source-aware confidence: Sentinel-2 real tiles carry a 1.1× boost
    over stub/manual sources.
  • image_date aware: uses `image_date` (if set) for temporal distance
    calculation, falling back to observation_end → created_at.
  • Backward-compatible: all v1 metadata keys are still emitted so
    existing dashboards don't break.  A `fusion_rule_version` key
    distinguishes v2 payloads.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories import create_alert, distance_meters, fused_alert_exists, list_alerts, list_satellite_changes
from app.schemas import Alert, AlertCreate, AlertType, FusionRunRequest, FusionRunResponse, SatelliteChangeSource
from app.services.audio_classifier import model_domain_for_version

# ---------------------------------------------------------------------------
# Version tag — bump whenever scoring logic changes
# ---------------------------------------------------------------------------
FUSION_RULE_VERSION = "rule-fusion-v2"

# Base weights (applied before decay factors)
ACOUSTIC_WEIGHT = 0.45
SATELLITE_SEVERITY_WEIGHT = 0.35
SATELLITE_CONFIDENCE_WEIGHT = 0.10
RECURRENCE_WEIGHT = 0.10

# Source quality multipliers for satellite confidence
_SOURCE_QUALITY: dict[str, float] = {
    SatelliteChangeSource.sentinel_2.value: 1.10,
    SatelliteChangeSource.manual.value: 1.00,
    SatelliteChangeSource.csv_ndvi.value: 0.95,
    SatelliteChangeSource.sentinel_stub.value: 0.75,
    SatelliteChangeSource.landsat_stub.value: 0.75,
    SatelliteChangeSource.ndvi_stub.value: 0.70,
}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _priority(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _temporal_decay(event_time: datetime, reference_time: datetime, halflife_days: float) -> float:
    """Exponential decay factor: 1.0 at t=0, 0.5 at t=halflife, → 0 as t→∞.

    Returns a value in (0, 1].  Uses the absolute time gap so that events
    *after* the acoustic alert are also down-weighted symmetrically.
    """
    gap_days = abs((event_time - reference_time).total_seconds()) / 86_400.0
    return 2.0 ** (-gap_days / halflife_days)


def _spatial_decay(distance_m: float, sigma_m: float) -> float:
    """Gaussian proximity factor: 1.0 at d=0, 1/sqrt(e)≈0.607 at d=sigma."""
    return math.exp(-0.5 * (distance_m / sigma_m) ** 2)


def _best_event_time(change: Any) -> datetime:
    """Return the most precise observation timestamp available for a change."""
    return (
        change.image_date
        or change.observation_end
        or change.observation_start
        or change.created_at
    )


def _within_window(alert_time: datetime, change: Any, days: int) -> bool:
    """Coarse pre-filter: is the satellite event within the time window?"""
    window = timedelta(days=days)
    start = change.observation_start or change.created_at
    end = change.observation_end or change.created_at
    return (start - window) <= alert_time <= (end + window)


def _source_quality(change: Any) -> float:
    return _SOURCE_QUALITY.get(change.source.value, 1.0)


def _compound_satellite_signal(satellite_contributions: list[float]) -> float:
    """Combine N independent satellite evidence probabilities with diminishing returns.

    Uses the probabilistic union: 1 - product(1 - p_i), which is the
    probability that *at least one* satellite piece of evidence is real.
    Caps at 1.0 numerically.
    """
    if not satellite_contributions:
        return 0.0
    product = 1.0
    for p in satellite_contributions:
        product *= 1.0 - min(p, 1.0)
    return min(1.0 - product, 1.0)


# ---------------------------------------------------------------------------
# Main fusion entry-point
# ---------------------------------------------------------------------------

def run_fusion(org_id: int, request: FusionRunRequest) -> FusionRunResponse:
    acoustic_alerts = list_alerts(org_id=org_id, alert_type=AlertType.audio, region_id=request.region_id)
    satellite_changes = [
        change
        for change in list_satellite_changes(org_id, region_id=request.region_id)
        if change.severity_score >= request.min_satellite_severity
        and change.latitude is not None
        and change.longitude is not None
    ]
    matched_count = 0
    created: list[Alert] = []
    now = datetime.now(timezone.utc)

    for alert in acoustic_alerts:
        # ── Candidate matching ─────────────────────────────────────────────
        candidates: list[tuple[Any, float, float, float]] = []
        # (change, distance_m, temporal_decay, spatial_decay)

        for change in satellite_changes:
            # Region guard: skip cross-region matches when both are set
            if (
                change.region_id is not None
                and alert.region_id is not None
                and change.region_id != alert.region_id
            ):
                continue

            # Coarse time-window pre-filter (keeps DB-level semantics compatible)
            if not _within_window(alert.created_at, change, request.time_window_days):
                continue

            distance = distance_meters(
                alert.location.lat,
                alert.location.lon,
                float(change.latitude),
                float(change.longitude),
            )
            if distance > request.distance_meters:
                continue  # Outside hard spatial limit

            event_time = _best_event_time(change)
            t_decay = _temporal_decay(event_time, alert.created_at, request.time_decay_halflife_days)
            s_decay = _spatial_decay(distance, request.spatial_sigma_meters)
            candidates.append((change, distance, t_decay, s_decay))

        if not candidates:
            continue

        matched_count += 1

        # Pick the single best corroborating change (highest combined decay weight)
        best_change, best_distance, best_t_decay, best_s_decay = max(
            candidates,
            key=lambda x: x[2] * x[3] * x[0].severity_score,
        )

        if fused_alert_exists(org_id, alert.id, best_change.id):
            continue

        # ── Acoustic signal ────────────────────────────────────────────────
        acoustic_confidence = alert.classifier_confidence or 0.0
        acoustic_suppressed = acoustic_confidence < request.min_acoustic_confidence
        acoustic_weight = 0.0 if acoustic_suppressed else ACOUSTIC_WEIGHT
        # Apply temporal decay to acoustic contribution too
        acoustic_t_decay = _temporal_decay(alert.created_at, now, request.time_decay_halflife_days)
        acoustic_contribution = acoustic_weight * acoustic_confidence * acoustic_t_decay

        # ── Satellite signal compounding ───────────────────────────────────
        # Build a probability for each candidate satellite change, then compound
        satellite_probs: list[float] = []
        for change, dist, t_dec, s_dec in candidates:
            sq = _source_quality(change)
            base_sat_score = (
                SATELLITE_SEVERITY_WEIGHT * change.severity_score
                + SATELLITE_CONFIDENCE_WEIGHT * change.confidence * sq
            )
            # Apply spatiotemporal decay factors
            sat_contribution = base_sat_score * t_dec * s_dec
            satellite_probs.append(sat_contribution)

        satellite_signal = _compound_satellite_signal(satellite_probs)

        # ── Recurrence bonus ───────────────────────────────────────────────
        recurrence_bonus = min(0.1 * math.log1p(len(candidates) - 1), 0.15)

        fusion_score = min(
            acoustic_contribution + satellite_signal + RECURRENCE_WEIGHT * recurrence_bonus,
            1.0,
        )

        # ── Metadata ───────────────────────────────────────────────────────
        model_domain = _model_domain(alert)
        metadata: dict[str, Any] = {
            # v1-compatible keys
            "acoustic_alert_id": alert.id,
            "satellite_change_id": best_change.id,
            "acoustic_confidence": acoustic_confidence,
            "acoustic_confidence_threshold": request.min_acoustic_confidence,
            "acoustic_suppressed": acoustic_suppressed,
            "acoustic_weight": acoustic_weight,
            "acoustic_score_contribution": round(acoustic_contribution, 4),
            "satellite_severity_score": best_change.severity_score,
            "satellite_severity_weight": SATELLITE_SEVERITY_WEIGHT,
            "satellite_confidence": best_change.confidence,
            "satellite_confidence_weight": SATELLITE_CONFIDENCE_WEIGHT,
            "recurrence_weight": RECURRENCE_WEIGHT,
            "distance_meters": round(best_distance, 2),
            "fusion_score": round(fusion_score, 4),
            "fusion_scoring_mode": "satellite_only" if acoustic_suppressed else "acoustic_satellite",
            "fusion_rule_version": FUSION_RULE_VERSION,
            "created_at": now.isoformat(),
            # v2-specific keys
            "temporal_decay": round(best_t_decay, 4),
            "spatial_decay": round(best_s_decay, 4),
            "time_decay_halflife_days": request.time_decay_halflife_days,
            "spatial_sigma_meters": request.spatial_sigma_meters,
            "corroborating_change_count": len(candidates),
            "satellite_compound_signal": round(satellite_signal, 4),
            "source_quality_multiplier": round(_source_quality(best_change), 4),
        }
        if model_domain:
            metadata["model_domain"] = model_domain

        # Carry through NDVI provenance from the best satellite change
        for key in ("baseline_ndvi", "recent_ndvi", "ndvi_delta", "ingestion_batch_id", "loss_threshold", "row_number"):
            if best_change.metadata and key in best_change.metadata:
                metadata[key] = best_change.metadata[key]

        description = (
            f"Fusion alert: acoustic evidence '{alert.classifier_label or 'audio'}' "
            f"matched {len(candidates)} satellite change(s) — best: "
            f"'{best_change.change_type.value}' within {round(best_distance)}m "
            f"(temporal decay {best_t_decay:.2f}, spatial decay {best_s_decay:.2f})."
        )

        created.append(
            create_alert(
                org_id,
                AlertCreate(
                    type=AlertType.fusion,
                    sensor_id=alert.sensor_id,
                    region_id=alert.region_id or best_change.region_id,
                    location=alert.location,
                    description=description,
                    priority=_priority(fusion_score),
                    classifier_label=alert.classifier_label,
                    classifier_confidence=alert.classifier_confidence,
                    classifier_model_version=alert.classifier_model_version,
                    metadata=metadata,
                ),
            )
        )

    return FusionRunResponse(created_count=len(created), matched_count=matched_count, alerts=created)


def _model_domain(alert: Alert) -> str | None:
    if alert.metadata and alert.metadata.get("model_domain"):
        return str(alert.metadata["model_domain"])
    return model_domain_for_version(alert.classifier_model_version)
