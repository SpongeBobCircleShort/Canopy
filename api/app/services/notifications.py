"""Webhook and email notification dispatcher.

Fires JSON webhooks and SMTP emails when a high/critical alert is created.
Errors are logged and never surfaced to the caller — notifications are best-effort.
"""
from __future__ import annotations

import json
import logging
import smtplib
import urllib.request
from email.message import EmailMessage
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


def _send_email(alert: Any, recipients: list[str]) -> None:
    from app.config import get_settings
    settings = get_settings()
    if not settings.smtp_host:
        return
    from_addr = settings.smtp_from_address or settings.smtp_user or "canopy@example.com"
    subject = f"[Canopy] {alert.priority.upper()} alert: {alert.description[:80]}"
    body = (
        f"A {alert.priority} alert was created.\n\n"
        f"Type: {alert.type.value if hasattr(alert.type, 'value') else alert.type}\n"
        f"Description: {alert.description}\n"
        f"Location: {alert.location.lat}, {alert.location.lon}\n"
        f"Created: {alert.created_at.isoformat() if alert.created_at else 'unknown'}\n"
    )
    if alert.classifier_label:
        body += f"Classifier: {alert.classifier_label} ({alert.classifier_confidence:.0%})\n"

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg.set_content(body)

    for recipient in recipients:
        if not recipient or "@" not in recipient:
            continue
        msg.replace_header("To", recipient) if "To" in msg else msg["To"].__class__  # handled below
        try:
            individual = EmailMessage()
            individual["From"] = from_addr
            individual["To"] = recipient
            individual["Subject"] = subject
            individual.set_content(body)
            if settings.smtp_use_tls:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_TIMEOUT_SECONDS) as smtp:
                    smtp.starttls()
                    if settings.smtp_user and settings.smtp_password:
                        smtp.login(settings.smtp_user, settings.smtp_password)
                    smtp.send_message(individual)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_TIMEOUT_SECONDS) as smtp:
                    if settings.smtp_user and settings.smtp_password:
                        smtp.login(settings.smtp_user, settings.smtp_password)
                    smtp.send_message(individual)
        except Exception as exc:
            log.warning("Email delivery failed for %s: %s", recipient, exc)


def notify_alert_created(alert: Any, webhooks: list[str], emails: list[str] | None = None) -> None:
    """Fire webhooks and emails for high/critical alerts. Silently skips lower priorities."""
    if alert.priority not in _NOTIFY_PRIORITIES:
        return
    if webhooks:
        payload = _alert_payload(alert)
        for url in webhooks:
            if url and url.startswith(("http://", "https://")):
                _post_webhook(url, payload)
    if emails:
        _send_email(alert, emails)
