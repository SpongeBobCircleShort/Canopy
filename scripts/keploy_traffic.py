"""Exercise the Canopy API so Keploy can record real traffic into test cases.

Keploy generates its test suite (and data mocks) by capturing live API calls, so
the quality of the recorded tests depends entirely on the traffic it sees. This
script walks the API the way a real operator does: sign up an org, create a
region and sensors, post alerts and satellite changes, filter and export, run
fusion, and check health.

Usage (see docs/keploy.md for the full flow):

    # terminal 1: record
    keploy record -c "docker compose up" --containerName canopy-api

    # terminal 2: generate the traffic Keploy will turn into tests
    python scripts/keploy_traffic.py --base-url http://localhost:8000

Standalone, it doubles as a smoke test of the API surface.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
import uuid
from typing import Any

TIMEOUT = 30


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.calls = 0
        self.failures = 0

    def request(self, method: str, path: str, body: dict | None = None, expect: int | None = None) -> Any:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            print(f"  {method} {path} -> ERROR {exc}")
            return None
        ok = expect is None or status == expect
        if not ok:
            self.failures += 1
        print(f"  {method:6s} {path:42s} -> {status} {'' if ok else '(expected ' + str(expect) + ')'}")
        try:
            return json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return raw


def run(base_url: str) -> int:
    api = ApiClient(base_url)
    suffix = uuid.uuid4().hex[:8]

    print("health + auth")
    api.request("GET", "/api/health", expect=200)
    signup = api.request(
        "POST", "/api/auth/signup",
        {"name": "Keploy Ranger", "email": f"keploy_{suffix}@example.org",
         "password": "correct-horse-battery", "organization_name": f"Keploy Org {suffix}"},
        expect=201,
    )
    if not signup or "access_token" not in signup:
        print("signup failed; aborting")
        return 1
    api.token = signup["access_token"]
    api.request("GET", "/api/auth/me", expect=200)

    print("regions + sensors")
    region = api.request("POST", "/api/regions", {"name": f"Kanha Buffer {suffix}", "description": "Keploy traffic"}, expect=201)
    region_id = (region or {}).get("id")
    sensor = api.request(
        "POST", "/api/sensors",
        {"name": f"KNH-{suffix}", "region_id": region_id, "location": {"lat": 22.30, "lon": 80.60}},
        expect=201,
    )
    sensor_id = (sensor or {}).get("id")
    api.request("GET", "/api/regions", expect=200)
    api.request("GET", "/api/sensors", expect=200)

    print("alerts")
    alert = api.request(
        "POST", "/api/alerts",
        {"type": "audio", "sensor_id": sensor_id, "region_id": region_id,
         "location": {"lat": 22.301, "lon": 80.601},
         "description": "Chainsaw detected near KNH sensor.", "priority": "high"},
        expect=201,
    )
    alert_id = (alert or {}).get("id")
    api.request("GET", "/api/alerts", expect=200)
    api.request("GET", "/api/alerts?priority=high&status=open", expect=200)
    if alert_id:
        api.request("PATCH", f"/api/alerts/{alert_id}/status", {"status": "acknowledged"}, expect=200)
        api.request("GET", f"/api/alerts/{alert_id}", expect=200)
    api.request("GET", "/api/alerts/export?format=csv", expect=200)

    print("satellite changes + fusion")
    api.request(
        "POST", "/api/satellite-changes",
        {"region_id": region_id, "source": "manual", "change_type": "canopy_loss",
         "severity_score": 0.82, "confidence": 0.9, "latitude": 22.3015, "longitude": 80.6015,
         "description": "Canopy loss adjacent to acoustic detection."},
        expect=201,
    )
    api.request("GET", "/api/satellite-changes", expect=200)
    api.request("POST", "/api/fusion/run", {"region_id": region_id}, expect=200)
    api.request(
        "POST", "/api/satellite-changes/ingest-embedding",
        {"bbox": [80.5, 22.2, 80.7, 22.4], "baseline_year": 2019, "recent_year": 2023, "grid_resolution": 4},
        expect=202,
    )

    print("negative paths (Keploy records these too)")
    api.request("GET", "/api/alerts/999999", expect=404)
    api.request("POST", "/api/auth/login", {"email": "nobody@example.org", "password": "wrong"}, expect=401)

    print(f"\n{api.calls} calls, {api.failures} unexpected")
    return 1 if api.failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Canopy API traffic for Keploy to record.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    raise SystemExit(run(args.base_url))


if __name__ == "__main__":
    main()
