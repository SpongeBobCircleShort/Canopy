"""Automatic fusion scheduler.

When FUSION_AUTO_INTERVAL_MINUTES > 0, a background asyncio task runs fusion
for every organisation every N minutes.  Results are logged; any high/critical
fused alerts automatically trigger configured webhooks via the normal path.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

_state: dict[str, Any] = {
    "interval_minutes": 0,
    "last_run_at": None,
    "last_run_created": 0,
    "last_run_matched": 0,
    "last_run_orgs": 0,
    "task": None,
}


def get_schedule_status() -> dict[str, Any]:
    return {
        "interval_minutes": _state["interval_minutes"],
        "enabled": _state["interval_minutes"] > 0,
        "last_run_at": _state["last_run_at"].isoformat() if _state["last_run_at"] else None,
        "last_run_created": _state["last_run_created"],
        "last_run_matched": _state["last_run_matched"],
        "last_run_orgs": _state["last_run_orgs"],
    }


def _run_fusion_all_orgs() -> tuple[int, int, int]:
    """Run fusion for every org. Returns (total_created, total_matched, org_count)."""
    from app.repositories import list_organizations
    from app.schemas import FusionRunRequest
    from app.services.fusion import run_fusion

    orgs = list_organizations()
    total_created, total_matched = 0, 0
    for org in orgs:
        try:
            result = run_fusion(org.id, FusionRunRequest())
            total_created += result.created_count
            total_matched += result.matched_count
        except Exception as exc:
            log.warning("Scheduled fusion failed for org %s: %s", org.id, exc)
    return total_created, total_matched, len(orgs)


async def _fusion_loop(interval_seconds: float) -> None:
    log.info("Fusion scheduler started (interval=%ss)", interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        log.info("Running scheduled fusion across all organisations…")
        try:
            created, matched, orgs = await asyncio.to_thread(_run_fusion_all_orgs)
            _state["last_run_at"] = datetime.now(timezone.utc)
            _state["last_run_created"] = created
            _state["last_run_matched"] = matched
            _state["last_run_orgs"] = orgs
            log.info("Scheduled fusion complete: %s org(s), %s alert(s) created, %s match(es)", orgs, created, matched)
        except Exception as exc:
            log.error("Scheduled fusion loop error: %s", exc)


def start_scheduler(interval_minutes: int) -> None:
    if interval_minutes <= 0:
        return
    _state["interval_minutes"] = interval_minutes
    loop = asyncio.get_event_loop()
    task = loop.create_task(_fusion_loop(interval_minutes * 60))
    _state["task"] = task
    log.info("Fusion auto-scheduler registered (every %s min)", interval_minutes)


def stop_scheduler() -> None:
    task = _state.get("task")
    if task and not task.done():
        task.cancel()
        _state["task"] = None
