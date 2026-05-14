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
