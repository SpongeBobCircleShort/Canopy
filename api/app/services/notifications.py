"""Webhook notification dispatcher.

Fires a JSON POST to each configured URL when a high/critical alert is created.
Errors are logged and never surfaced to the caller — notifications are best-effort.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

_NOTIFY_PRIORITIES = {"high", "critical"}
_TIMEOUT_SECONDS = 5


def _alert_payload(alert: Any) -> dict:
    return {
        "event": "alert.created",
        "alert": {
            "id": alert.id,
            "type": alert.type.value if hasattr(alert.type, "value") else alert.type,
            "priority": alert.priority,
            "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
            "description": alert.description,
            "latitude": alert.location.lat if alert.location else None,
            "longitude": alert.location.lon if alert.location else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "classifier_label": alert.classifier_label,
            "classifier_confidence": alert.classifier_confidence,
        },
    }


def _post_webhook(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Canopy/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            status = resp.getcode()
            if status >= 400:
                log.warning("Webhook %s returned HTTP %s", url, status)
    except Exception as exc:
        log.warning("Webhook delivery failed for %s: %s", url, exc)


def notify_alert_created(alert: Any, webhooks: list[str]) -> None:
    """Fire webhooks for high/critical alerts. Silently skips lower priorities."""
    if not webhooks or alert.priority not in _NOTIFY_PRIORITIES:
        return
    payload = _alert_payload(alert)
    for url in webhooks:
        if url and url.startswith(("http://", "https://")):
            _post_webhook(url, payload)
