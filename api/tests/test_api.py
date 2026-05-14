import base64
import csv
import json
import os
from io import StringIO
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test-canopy.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["AUDIO_STORAGE_PATH"] = "./test-audio"

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _reset_test_database() -> None:
    get_settings.cache_clear()
    Path("test-canopy.db").unlink(missing_ok=True)
    audio_dir = Path("test-audio")
    if audio_dir.exists():
        for file_path in audio_dir.iterdir():
            file_path.unlink()


def _decode_payload(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode()))


def _signup(client: TestClient, email: str = "ranger@example.org", org_name: str = "Org A") -> str:
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test Ranger",
            "email": email,
            "password": "correct-horse-battery",
            "organization_name": org_name,
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_region(client: TestClient, token: str, name: str = "North Sector") -> dict:
    response = client.post(
        "/api/regions",
        headers=_auth_header(token),
        json={"name": name, "description": "Test region"},
    )
    assert response.status_code == 201
    return response.json()


def _create_sensor(
    client: TestClient,
    token: str,
    name: str = "FLU-TEST",
    lat: float = 1.25,
    lon: float = 2.5,
    region_id: int | None = None,
) -> dict:
    response = client.post(
        "/api/sensors",
        headers=_auth_header(token),
        json={"name": name, "region_id": region_id, "location": {"lat": lat, "lon": lon}},
    )
    assert response.status_code == 201
    return response.json()


def _create_alert(client: TestClient, token: str, lat: float, lon: float, sensor_id: int | None = None) -> dict:
    response = client.post(
        "/api/alerts",
        headers=_auth_header(token),
        json={
            "type": "satellite",
            "sensor_id": sensor_id,
            "location": {"lat": lat, "lon": lon},
            "description": "NDVI drop detected in test region.",
            "priority": "high",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health_endpoint() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "canopy-api"}


def test_signup_creates_organization_and_token_includes_org_id() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, org_name="Canopy Test Org")
        payload = _decode_payload(token)
        assert payload["role"] == "admin"
        assert payload["org_id"] is not None
        me = client.get("/api/auth/me", headers=_auth_header(token))
        assert me.status_code == 200
        assert me.json()["organization"]["name"] == "Canopy Test Org"


def test_org_scoped_regions_and_cross_org_region_rejected_for_sensor() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token_a = _signup(client, email="a@example.org", org_name="Org A")
        token_b = _signup(client, email="b@example.org", org_name="Org B")
        region_a = _create_region(client, token_a, "A Region")
        region_b = _create_region(client, token_b, "B Region")

        list_a = client.get("/api/regions", headers=_auth_header(token_a))
        assert [region["id"] for region in list_a.json()] == [region_a["id"]]

        cross_org_sensor = client.post(
            "/api/sensors",
            headers=_auth_header(token_a),
            json={"name": "Bad Sensor", "region_id": region_b["id"], "location": {"lat": 0, "lon": 0}},
        )
        assert cross_org_sensor.status_code == 404


def test_users_cannot_see_or_mutate_cross_org_sensors_alerts_or_clips() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token_a = _signup(client, email="a@example.org", org_name="Org A")
        token_b = _signup(client, email="b@example.org", org_name="Org B")
        sensor_a = _create_sensor(client, token_a, name="A Sensor", lat=-3.0, lon=-60.0)
        sensor_b = _create_sensor(client, token_b, name="B Sensor", lat=10.0, lon=20.0)
        alert_b = _create_alert(client, token_b, 10.0, 20.0, sensor_id=sensor_b["id"])

        sensors_a = client.get("/api/sensors", headers=_auth_header(token_a))
        assert [sensor["id"] for sensor in sensors_a.json()] == [sensor_a["id"]]

        cross_clip = client.post(
            "/api/clips/upload",
            headers=_auth_header(token_a),
            data={"sensor_id": str(sensor_b["id"])},
            files={"file": ("chainsaw.wav", b"RIFF....WAVE", "audio/wav")},
        )
        assert cross_clip.status_code == 404

        cross_status = client.patch(
            f"/api/alerts/{alert_b['id']}/status",
            headers=_auth_header(token_a),
            json={"status": "resolved"},
        )
        assert cross_status.status_code == 404


def test_alert_status_update_requires_admin_auth_and_validates_status() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client)
        alert = _create_alert(client, token, -3.1, -60.2)

        unauthorized = client.patch(f"/api/alerts/{alert['id']}/status", json={"status": "acknowledged"})
        assert unauthorized.status_code == 401

        invalid = client.patch(
            f"/api/alerts/{alert['id']}/status",
            headers=_auth_header(token),
            json={"status": "not-a-status"},
        )
        assert invalid.status_code == 422

        updated = client.patch(
            f"/api/alerts/{alert['id']}/status",
            headers=_auth_header(token),
            json={"status": "investigating", "note": "Ranger dispatched"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "investigating"
        assert updated.json()["status_note"] == "Ranger dispatched"
        assert updated.json()["updated_at"] is not None


def test_alert_filters_bbox_status_type_and_sensor_id_in_sqlite() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client)
        sensor = _create_sensor(client, token, lat=-3.0, lon=-60.0)
        inside = _create_alert(client, token, -3.2, -60.1, sensor_id=sensor["id"])
        _create_alert(client, token, 10.0, 20.0)
        client.patch(f"/api/alerts/{inside['id']}/status", headers=_auth_header(token), json={"status": "acknowledged"})

        response = client.get(
            "/api/alerts",
            headers=_auth_header(token),
            params={
                "bbox": "-61,-4,-59,-2",
                "status": "acknowledged",
                "type": "satellite",
                "sensor_id": sensor["id"],
            },
        )
        assert response.status_code == 200
        alerts = response.json()
        assert len(alerts) == 1
        assert alerts[0]["id"] == inside["id"]


def test_csv_export_only_contains_current_org_alerts() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token_a = _signup(client, email="a@example.org", org_name="Org A")
        token_b = _signup(client, email="b@example.org", org_name="Org B")
        _create_alert(client, token_a, -3.1, -60.2)
        _create_alert(client, token_b, 10.0, 20.0)

        response = client.get("/api/alerts/export", headers=_auth_header(token_a), params={"format": "csv"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "canopy-alerts.csv" in response.headers["content-disposition"]
        rows = list(csv.DictReader(StringIO(response.text)))
        assert len(rows) == 1
        assert rows[0]["latitude"] == "-3.1"
        assert set(rows[0].keys()) == {
            "id",
            "type",
            "status",
            "priority",
            "description",
            "latitude",
            "longitude",
            "sensor_id",
            "created_at",
            "classifier_label",
            "classifier_confidence",
            "fusion_score",
            "acoustic_alert_id",
            "satellite_change_id",
            "baseline_ndvi",
            "recent_ndvi",
            "ndvi_delta",
            "ingestion_batch_id",
            "metadata",
        }


def test_upload_clip_uses_classifier_service_and_generates_sensor_alert() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client)
        sensor = _create_sensor(client, token, name="FLU-AUDIO", lat=-4.0, lon=-61.0)

        missing_sensor = client.post(
            "/api/clips/upload",
            headers=_auth_header(token),
            files={"file": ("chainsaw.wav", b"RIFF....WAVE", "audio/wav")},
        )
        assert missing_sensor.status_code == 400

        empty_file = client.post(
            "/api/clips/upload",
            headers=_auth_header(token),
            data={"sensor_id": str(sensor["id"])},
            files={"file": ("chainsaw.wav", b"", "audio/wav")},
        )
        assert empty_file.status_code == 400

        response = client.post(
            "/api/clips/upload",
            headers=_auth_header(token),
            data={"sensor_id": str(sensor["id"])},
            files={"file": ("chainsaw.wav", b"RIFF....WAVE", "audio/wav")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["sensor_id"] == sensor["id"]
        assert body["classifier_label"] == "chainsaw"
        assert body["generated_alert"]["sensor_id"] == sensor["id"]
        assert body["generated_alert"]["classifier_label"] == "chainsaw"
        assert body["generated_alert"]["location"] == sensor["location"]


def test_e2e_org_scoped_mvp_flow() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        signup_token = _signup(client, email="e2e@example.org", org_name="E2E Org")
        login = client.post("/api/auth/login", json={"email": "e2e@example.org", "password": "correct-horse-battery"})
        assert login.status_code == 200
        token = login.json()["access_token"] or signup_token

        region = _create_region(client, token, name="E2E Region")
        sensor = _create_sensor(client, token, name="FLU-E2E", lat=-3.5, lon=-60.5, region_id=region["id"])
        upload = client.post(
            "/api/clips/upload",
            headers=_auth_header(token),
            data={"sensor_id": str(sensor["id"])},
            files={"file": ("unknown.wav", b"RIFF....WAVE", "audio/wav")},
        )
        assert upload.status_code == 201
        alert_id = upload.json()["generated_alert"]["id"]
        assert upload.json()["generated_alert"]["region_id"] == region["id"]

        alerts = client.get("/api/alerts", headers=_auth_header(token), params={"sensor_id": sensor["id"], "type": "audio"})
        assert alerts.status_code == 200
        assert alerts.json()[0]["id"] == alert_id

        status_update = client.patch(
            f"/api/alerts/{alert_id}/status",
            headers=_auth_header(token),
            json={"status": "resolved", "note": "Demo flow verified"},
        )
        assert status_update.status_code == 200
        assert status_update.json()["status"] == "resolved"

        export = client.get("/api/alerts/export", headers=_auth_header(token), params={"format": "csv", "sensor_id": sensor["id"]})
        assert export.status_code == 200
        assert "Audio classifier detected" in export.text


def _org_id(client: TestClient, token: str) -> int:
    response = client.get("/api/auth/me", headers=_auth_header(token))
    assert response.status_code == 200
    return response.json()["org_id"]


def _create_invite(client: TestClient, token: str, org_id: int, email: str = "member@example.org") -> dict:
    response = client.post(
        f"/api/organizations/{org_id}/invites",
        headers=_auth_header(token),
        json={"email": email, "role": "member"},
    )
    assert response.status_code == 201
    return response.json()


def test_admin_can_create_list_and_revoke_invite() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, email="admin@example.org", org_name="Invite Org")
        org_id = _org_id(client, token)
        invite = _create_invite(client, token, org_id, email="pending@example.org")
        assert invite["status"] == "pending"
        assert invite["token"]

        listed = client.get(f"/api/organizations/{org_id}/invites", headers=_auth_header(token))
        assert listed.status_code == 200
        assert listed.json()[0]["email"] == "pending@example.org"
        assert "token" not in listed.json()[0]

        revoked = client.post(f"/api/organizations/{org_id}/invites/{invite['id']}/revoke", headers=_auth_header(token))
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"

        revoked_signup = client.post(
            "/api/auth/signup",
            json={"name": "Pending", "email": "pending@example.org", "password": "pw", "invite_token": invite["token"]},
        )
        assert revoked_signup.status_code == 400


def test_invited_user_signup_joins_existing_org_and_can_read_org_data() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        admin_token = _signup(client, email="admin@example.org", org_name="Shared Org")
        org_id = _org_id(client, admin_token)
        sensor = _create_sensor(client, admin_token, name="Shared Sensor", lat=-5, lon=-62)
        invite = _create_invite(client, admin_token, org_id, email="member@example.org")

        mismatch = client.post(
            "/api/auth/signup",
            json={"name": "Wrong", "email": "wrong@example.org", "password": "pw", "invite_token": invite["token"]},
        )
        assert mismatch.status_code == 400

        signup = client.post(
            "/api/auth/signup",
            json={"name": "Member", "email": "member@example.org", "password": "pw", "invite_token": invite["token"]},
        )
        assert signup.status_code == 201
        member_token = signup.json()["access_token"]
        payload = _decode_payload(member_token)
        assert payload["role"] == "member"
        assert payload["org_id"] == org_id

        reuse = client.post(
            "/api/auth/signup",
            json={"name": "Again", "email": "member2@example.org", "password": "pw", "invite_token": invite["token"]},
        )
        assert reuse.status_code == 400

        sensors = client.get("/api/sensors", headers=_auth_header(member_token))
        assert sensors.status_code == 200
        assert [item["id"] for item in sensors.json()] == [sensor["id"]]

        member_invite_attempt = client.post(
            f"/api/organizations/{org_id}/invites",
            headers=_auth_header(member_token),
            json={"email": "other@example.org", "role": "member"},
        )
        assert member_invite_attempt.status_code == 403


def test_cross_org_invite_access_is_rejected() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token_a = _signup(client, email="a@example.org", org_name="Org A")
        token_b = _signup(client, email="b@example.org", org_name="Org B")
        org_a = _org_id(client, token_a)
        org_b = _org_id(client, token_b)
        invite_b = _create_invite(client, token_b, org_b, email="bmember@example.org")

        create_cross = client.post(
            f"/api/organizations/{org_b}/invites",
            headers=_auth_header(token_a),
            json={"email": "bad@example.org", "role": "member"},
        )
        assert create_cross.status_code == 404

        list_cross = client.get(f"/api/organizations/{org_b}/invites", headers=_auth_header(token_a))
        assert list_cross.status_code == 404

        revoke_cross = client.post(f"/api/organizations/{org_b}/invites/{invite_b['id']}/revoke", headers=_auth_header(token_a))
        assert revoke_cross.status_code == 404
        assert org_a != org_b


def test_expired_invite_cannot_be_accepted_and_normal_signup_requires_org_name() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        no_org = client.post(
            "/api/auth/signup",
            json={"name": "No Org", "email": "noorg@example.org", "password": "pw"},
        )
        assert no_org.status_code == 400

        admin_token = _signup(client, email="admin@example.org", org_name="Expiry Org")
        org_id = _org_id(client, admin_token)
        invite = _create_invite(client, admin_token, org_id, email="expired@example.org")

        from app.db import connection

        with connection() as conn:
            conn.execute("UPDATE organization_invites SET expires_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", invite["id"]))

        expired = client.post(
            "/api/auth/signup",
            json={"name": "Expired", "email": "expired@example.org", "password": "pw", "invite_token": invite["token"]},
        )
        assert expired.status_code == 400


def _signup_member(client: TestClient, admin_token: str, email: str = "member2@example.org") -> str:
    org_id = _org_id(client, admin_token)
    invite = _create_invite(client, admin_token, org_id, email=email)
    response = client.post(
        "/api/auth/signup",
        json={"name": "Member", "email": email, "password": "pw", "invite_token": invite["token"]},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _create_satellite_change(
    client: TestClient,
    token: str,
    lat: float = -3.0005,
    lon: float = -60.0005,
    region_id: int | None = None,
    severity_score: float = 0.8,
    confidence: float = 0.9,
) -> dict:
    response = client.post(
        "/api/satellite-changes",
        headers=_auth_header(token),
        json={
            "region_id": region_id,
            "source": "manual",
            "change_type": "canopy_loss",
            "severity_score": severity_score,
            "confidence": confidence,
            "latitude": lat,
            "longitude": lon,
            "description": "Manual canopy-loss observation for fusion test.",
        },
    )
    assert response.status_code == 201
    return response.json()


def _upload_chainsaw_clip(client: TestClient, token: str, sensor_id: int) -> dict:
    response = client.post(
        "/api/clips/upload",
        headers=_auth_header(token),
        data={"sensor_id": str(sensor_id)},
        files={"file": ("chainsaw.wav", b"RIFF....WAVE", "audio/wav")},
    )
    assert response.status_code == 201
    return response.json()["generated_alert"]


def _run_fusion(client: TestClient, token: str, payload: dict | None = None) -> dict:
    response = client.post(
        "/api/fusion/run",
        headers=_auth_header(token),
        json=payload
        or {
            "time_window_days": 14,
            "distance_meters": 500,
            "min_acoustic_confidence": 0.65,
            "min_satellite_severity": 0.3,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_satellite_change_admin_member_validation_and_org_scope() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        admin_a = _signup(client, email="sat-admin-a@example.org", org_name="Sat Org A")
        admin_b = _signup(client, email="sat-admin-b@example.org", org_name="Sat Org B")
        member_a = _signup_member(client, admin_a, email="sat-member-a@example.org")
        region_a = _create_region(client, admin_a, "A Satellite Region")
        region_b = _create_region(client, admin_b, "B Satellite Region")

        change_a = _create_satellite_change(client, admin_a, region_id=region_a["id"])

        member_create = client.post(
            "/api/satellite-changes",
            headers=_auth_header(member_a),
            json={"severity_score": 0.5, "confidence": 0.5, "latitude": -3, "longitude": -60},
        )
        assert member_create.status_code == 403

        member_list = client.get("/api/satellite-changes", headers=_auth_header(member_a))
        assert member_list.status_code == 200
        assert [change["id"] for change in member_list.json()] == [change_a["id"]]

        hidden_from_other_org = client.get(f"/api/satellite-changes/{change_a['id']}", headers=_auth_header(admin_b))
        assert hidden_from_other_org.status_code == 404
        other_org_list = client.get("/api/satellite-changes", headers=_auth_header(admin_b))
        assert other_org_list.status_code == 200
        assert other_org_list.json() == []

        invalid_severity = client.post(
            "/api/satellite-changes",
            headers=_auth_header(admin_a),
            json={"severity_score": 1.5, "confidence": 0.5, "latitude": -3, "longitude": -60},
        )
        assert invalid_severity.status_code == 422

        invalid_confidence = client.post(
            "/api/satellite-changes",
            headers=_auth_header(admin_a),
            json={"severity_score": 0.5, "confidence": -0.1, "latitude": -3, "longitude": -60},
        )
        assert invalid_confidence.status_code == 422

        cross_region = client.post(
            "/api/satellite-changes",
            headers=_auth_header(admin_a),
            json={"region_id": region_b["id"], "severity_score": 0.5, "confidence": 0.5, "latitude": -3, "longitude": -60},
        )
        assert cross_region.status_code == 404

        delete_as_member = client.delete(f"/api/satellite-changes/{change_a['id']}", headers=_auth_header(member_a))
        assert delete_as_member.status_code == 403
        delete_as_admin = client.delete(f"/api/satellite-changes/{change_a['id']}", headers=_auth_header(admin_a))
        assert delete_as_admin.status_code == 204


def test_fusion_creates_metadata_priority_and_avoids_duplicates() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, email="fusion@example.org", org_name="Fusion Org")
        region = _create_region(client, token)
        sensor = _create_sensor(client, token, lat=-3.0, lon=-60.0, region_id=region["id"])
        acoustic = _upload_chainsaw_clip(client, token, sensor["id"])
        satellite = _create_satellite_change(client, token, region_id=region["id"], severity_score=0.8, confidence=0.9)

        result = _run_fusion(client, token)
        assert result["matched_count"] == 1
        assert result["created_count"] == 1
        fused = result["alerts"][0]
        assert fused["type"] == "fusion"
        assert fused["priority"] == "high"
        assert fused["metadata"]["acoustic_alert_id"] == acoustic["id"]
        assert fused["metadata"]["satellite_change_id"] == satellite["id"]
        assert fused["metadata"]["acoustic_confidence"] == 0.82
        assert fused["metadata"]["satellite_severity_score"] == 0.8
        assert fused["metadata"]["satellite_confidence"] == 0.9
        assert fused["metadata"]["distance_meters"] <= 500
        assert abs(fused["metadata"]["fusion_score"] - 0.739) < 0.0001
        assert fused["metadata"]["fusion_rule_version"] == "rule-fusion-v0"

        listed = client.get("/api/alerts", headers=_auth_header(token), params={"type": "fusion"})
        assert listed.status_code == 200
        assert listed.json()[0]["metadata"]["satellite_change_id"] == satellite["id"]

        duplicate = _run_fusion(client, token)
        assert duplicate["matched_count"] == 1
        assert duplicate["created_count"] == 0


def test_fusion_respects_thresholds_and_org_boundaries() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token_a = _signup(client, email="threshold-a@example.org", org_name="Threshold A")
        token_b = _signup(client, email="threshold-b@example.org", org_name="Threshold B")
        sensor_a = _create_sensor(client, token_a, lat=-3.0, lon=-60.0)
        _upload_chainsaw_clip(client, token_a, sensor_a["id"])

        _create_satellite_change(client, token_a, lat=-4.0, lon=-61.0, severity_score=0.8, confidence=0.9)
        too_far = _run_fusion(client, token_a)
        assert too_far["matched_count"] == 0
        assert too_far["created_count"] == 0

        _create_satellite_change(client, token_a, lat=-3.0005, lon=-60.0005, severity_score=0.2, confidence=0.9)
        low_severity = _run_fusion(client, token_a)
        assert low_severity["matched_count"] == 0
        assert low_severity["created_count"] == 0

        high_conf_required = _run_fusion(client, token_a, {"time_window_days": 14, "distance_meters": 500, "min_acoustic_confidence": 0.95, "min_satellite_severity": 0.3})
        assert high_conf_required["matched_count"] == 0
        assert high_conf_required["created_count"] == 0

        # Org B has a nearby satellite change but no acoustic alert in its org, so no cross-org fusion occurs.
        _create_satellite_change(client, token_b, lat=-3.0005, lon=-60.0005, severity_score=0.9, confidence=0.9)
        org_b_result = _run_fusion(client, token_b)
        assert org_b_result["matched_count"] == 0
        assert org_b_result["created_count"] == 0

        member = _signup_member(client, token_a, email="fusion-member@example.org")
        forbidden = client.post("/api/fusion/run", headers=_auth_header(member), json={})
        assert forbidden.status_code == 403


def test_backend_manual_satellite_fusion_demo_flow_and_csv_metadata() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, email="demo-fusion@example.org", org_name="Demo Fusion Org")
        region = _create_region(client, token, "Demo Region")
        sensor = _create_sensor(client, token, lat=-3.0, lon=-60.0, region_id=region["id"])
        acoustic = _upload_chainsaw_clip(client, token, sensor["id"])
        assert acoustic["type"] == "audio"

        satellite = _create_satellite_change(client, token, region_id=region["id"], lat=-3.0005, lon=-60.0005)
        result = _run_fusion(client, token)
        assert result["created_count"] == 1
        fused = result["alerts"][0]
        assert fused["metadata"]["acoustic_alert_id"] == acoustic["id"]
        assert fused["metadata"]["satellite_change_id"] == satellite["id"]

        status_update = client.patch(
            f"/api/alerts/{fused['id']}/status",
            headers=_auth_header(token),
            json={"status": "investigating", "note": "Demo fused alert triaged"},
        )
        assert status_update.status_code == 200
        assert status_update.json()["status"] == "investigating"

        export = client.get("/api/alerts/export", headers=_auth_header(token), params={"format": "csv"})
        assert export.status_code == 200
        rows = list(csv.DictReader(StringIO(export.text)))
        fused_rows = [row for row in rows if row["type"] == "fusion"]
        assert len(fused_rows) == 1
        assert fused_rows[0]["fusion_score"]
        assert fused_rows[0]["acoustic_alert_id"] == str(acoustic["id"])
        assert fused_rows[0]["satellite_change_id"] == str(satellite["id"])
        assert "fusion_rule_version" in fused_rows[0]["metadata"]


def _upload_ndvi_csv(
    client: TestClient,
    token: str,
    csv_text: str,
    *,
    region_id: int | None = None,
    loss_threshold: float = -0.15,
    default_confidence: float = 0.75,
) -> dict:
    data = {"loss_threshold": str(loss_threshold), "default_confidence": str(default_confidence)}
    if region_id is not None:
        data["region_id"] = str(region_id)
    response = client.post(
        "/api/ndvi/upload-csv",
        headers=_auth_header(token),
        data=data,
        files={"file": ("ndvi.csv", csv_text.encode(), "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def test_ndvi_csv_upload_creates_changes_and_skips_non_loss_rows() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, email="ndvi@example.org", org_name="NDVI Org")
        region = _create_region(client, token)
        csv_text = "\n".join(
            [
                "latitude,longitude,baseline_ndvi,recent_ndvi,description,confidence",
                "-3.4654,-62.2160,0.72,0.48,large drop,0.91",
                "-3.4660,-62.2165,0.81,0.58,second drop,0.82",
                "-3.4670,-62.2170,0.60,0.50,small drop skipped,0.80",
                "-3.4680,-62.2180,0.40,0.52,positive skipped,0.80",
            ]
        )
        result = _upload_ndvi_csv(client, token, csv_text, region_id=region["id"])
        assert result["status"] == "processed"
        assert result["row_count"] == 4
        assert result["created_change_count"] == 2
        assert result["skipped_count"] == 2

        changes = client.get("/api/satellite-changes", headers=_auth_header(token))
        assert changes.status_code == 200
        assert len(changes.json()) == 2
        first = changes.json()[0]
        assert first["source"] == "csv_ndvi"
        assert first["change_type"] == "ndvi_drop"
        assert first["metadata"]["ingestion_batch_id"] == result["batch_id"]
        assert "ndvi_delta" in first["metadata"]


def test_ndvi_csv_validation_errors_fail_upload() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, email="ndvi-invalid@example.org", org_name="NDVI Invalid Org")
        invalid_cases = [
            "latitude,longitude,baseline_ndvi\n-3,-62,0.7\n",
            "latitude,longitude,baseline_ndvi,recent_ndvi\n-3,-62,1.2,0.5\n",
            "latitude,longitude,baseline_ndvi,recent_ndvi\n-95,-62,0.7,0.4\n",
            "latitude,longitude,baseline_ndvi,recent_ndvi,confidence\n-3,-62,0.7,0.4,1.5\n",
        ]
        for csv_text in invalid_cases:
            response = client.post(
                "/api/ndvi/upload-csv",
                headers=_auth_header(token),
                data={"loss_threshold": "-0.15", "default_confidence": "0.75"},
                files={"file": ("bad.csv", csv_text.encode(), "text/csv")},
            )
            assert response.status_code == 400


def test_ndvi_rbac_and_org_scoped_batches() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        admin_a = _signup(client, email="ndvi-admin-a@example.org", org_name="NDVI A")
        admin_b = _signup(client, email="ndvi-admin-b@example.org", org_name="NDVI B")
        member_a = _signup_member(client, admin_a, email="ndvi-member-a@example.org")
        region_a = _create_region(client, admin_a, "NDVI A Region")
        region_b = _create_region(client, admin_b, "NDVI B Region")
        csv_text = "latitude,longitude,baseline_ndvi,recent_ndvi\n-3.4654,-62.2160,0.72,0.48\n"

        member_upload = client.post(
            "/api/ndvi/upload-csv",
            headers=_auth_header(member_a),
            data={"region_id": str(region_a["id"])},
            files={"file": ("ndvi.csv", csv_text.encode(), "text/csv")},
        )
        assert member_upload.status_code == 403

        cross_region = client.post(
            "/api/ndvi/upload-csv",
            headers=_auth_header(admin_a),
            data={"region_id": str(region_b["id"])},
            files={"file": ("ndvi.csv", csv_text.encode(), "text/csv")},
        )
        assert cross_region.status_code == 404

        result = _upload_ndvi_csv(client, admin_a, csv_text, region_id=region_a["id"])
        member_batches = client.get("/api/ndvi/batches", headers=_auth_header(member_a))
        assert member_batches.status_code == 200
        assert [batch["id"] for batch in member_batches.json()] == [result["batch_id"]]

        other_org_batches = client.get("/api/ndvi/batches", headers=_auth_header(admin_b))
        assert other_org_batches.status_code == 200
        assert other_org_batches.json() == []

        hidden_batch = client.get(f"/api/ndvi/batches/{result['batch_id']}", headers=_auth_header(admin_b))
        assert hidden_batch.status_code == 404


def test_ndvi_csv_generated_change_fuses_with_acoustic_alert_and_exports_provenance() -> None:
    _reset_test_database()
    with TestClient(app) as client:
        token = _signup(client, email="ndvi-fusion@example.org", org_name="NDVI Fusion Org")
        region = _create_region(client, token)
        sensor = _create_sensor(client, token, lat=-3.4653, lon=-62.2159, region_id=region["id"])
        acoustic = _upload_chainsaw_clip(client, token, sensor["id"])
        csv_text = "latitude,longitude,baseline_ndvi,recent_ndvi,confidence\n-3.4654,-62.2160,0.72,0.48,0.9\n"
        ndvi = _upload_ndvi_csv(client, token, csv_text, region_id=region["id"])
        assert ndvi["created_change_count"] == 1

        result = _run_fusion(client, token)
        assert result["created_count"] == 1
        fused = result["alerts"][0]
        assert fused["metadata"]["acoustic_alert_id"] == acoustic["id"]
        assert fused["metadata"]["ingestion_batch_id"] == ndvi["batch_id"]
        assert fused["metadata"]["baseline_ndvi"] == 0.72
        assert fused["metadata"]["recent_ndvi"] == 0.48
        assert fused["metadata"]["ndvi_delta"] == -0.24

        export = client.get("/api/alerts/export", headers=_auth_header(token), params={"format": "csv"})
        assert export.status_code == 200
        rows = list(csv.DictReader(StringIO(export.text)))
        fused_rows = [row for row in rows if row["type"] == "fusion"]
        assert len(fused_rows) == 1
        assert fused_rows[0]["ingestion_batch_id"] == str(ndvi["batch_id"])
        assert fused_rows[0]["baseline_ndvi"] == "0.72"
        assert fused_rows[0]["recent_ndvi"] == "0.48"
        assert fused_rows[0]["ndvi_delta"] == "-0.24"
