from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.main import app, get_book
from api.app.storage import empty_book

HEADER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SHEET_ID", raising=False)
    book = empty_book()

    def override():
        yield book

    app.dependency_overrides[get_book] = override
    with TestClient(app) as client:
        yield client, book
    app.dependency_overrides.clear()


def test_health_is_open_and_writes_require_the_token(api):
    client, _book = api
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"ok": True}
    assert client.post("/notes", json={"client_request_id": "a", "raw_text": "x"}).status_code == 401
    assert client.post(
        "/notes",
        json={"client_request_id": "a", "raw_text": "x"},
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401


def test_notes_stay_pending_and_parse_does_not_touch_them(api):
    client, book = api
    missing = client.post("/notes", json={"raw_text": "bench"}, headers=HEADER)
    assert missing.status_code == 400
    first = client.post(
        "/notes",
        json={"client_request_id": "req-1", "raw_text": "bench", "session_date": "2026-09-22", "day_label": "Push"},
        headers=HEADER,
    )
    assert first.status_code == 200
    body = first.json()
    assert body["note"]["parse_status"] == "pending"
    assert body["sets"] == []
    second = client.post("/notes", json={"client_request_id": "req-1", "raw_text": "other"}, headers=HEADER)
    assert second.json()["note"]["id"] == body["note"]["id"]
    assert second.json()["note"]["raw_text"] == "bench"
    parsed = client.post(f"/notes/{body['note']['id']}/parse", headers=HEADER)
    assert parsed.status_code == 503
    assert book["Notes"][0]["parse_status"] == "pending"
    assert book["Sessions"] == []
    assert book["Sets"] == []


def test_day_put_is_partial_and_builds_the_daily_view(api):
    client, _book = api
    created = client.put("/days/2026-09-22", json={"bodyweight_lb": 180, "day_label": "Push"}, headers=HEADER)
    assert created.status_code == 200
    updated = client.put("/days/2026-09-22", json={"sleep_hours": None}, headers=HEADER)
    assert updated.json()["bodyweight_lb"] == "180"
    assert updated.json()["sleep_hours"] == ""
    zero = client.put("/days/2026-09-23", json={"bodyweight_lb": 0}, headers=HEADER)
    assert zero.json()["bodyweight_lb"] == "0"
    view = client.get("/daily-view/2026-09-22", headers=HEADER)
    assert view.status_code == 200
    assert view.json()["bodyweight_lb"] == "180"
    assert client.get("/days/1900-01-01", headers=HEADER).status_code == 404


def test_sets_by_date_kg_and_supplement_conflict(api):
    client, book = api
    session = client.post("/sessions", json={"date": "2026-09-22", "label": "Push"}, headers=HEADER)
    assert session.status_code == 200
    lifted = client.post(
        "/sets",
        json={"session_id": session.json()["id"], "weight_lb": 20, "unit_entered": "kg", "set_number": "1"},
        headers=HEADER,
    )
    assert lifted.status_code == 200
    assert lifted.json()["weight_lb"] == "44.09"
    listed = client.get("/sets", params={"date": "2026-09-22"}, headers=HEADER)
    assert len(listed.json()) == 1
    assert client.post("/sets", json={"set_type": "cardio"}, headers=HEADER).status_code == 400
    assert client.post(
        "/supplements",
        json={"date": "2026-09-22", "item": "Creatine", "dose": "5"},
        headers=HEADER,
    ).status_code == 200
    assert client.post(
        "/supplements",
        json={"date": "2026-09-22", "item": "creatine", "dose": "5"},
        headers=HEADER,
    ).status_code == 409
    removed = client.delete(f"/sets/{lifted.json()['id']}", headers=HEADER)
    assert removed.status_code == 204
    assert book["Sets"] == []


def test_every_catalog_tab_roundtrips(api):
    client, _book = api
    created = client.post(
        "/exercises",
        json={"canonical_name": "Squat", "status": "active", "primary_muscles": "quads"},
        headers=HEADER,
    )
    assert created.status_code == 200
    row_id = created.json()["id"]
    assert client.get(f"/exercises/{row_id}", headers=HEADER).json()["canonical_name"] == "Squat"
    patched = client.patch(f"/exercises/{row_id}", json={"equipment": "rack"}, headers=HEADER)
    assert patched.json()["equipment"] == "rack"
    assert client.post(
        "/aliases",
        json={"alias": "Incline Dumbell", "exercise_id": row_id, "day_label": "Push"},
        headers=HEADER,
    ).status_code == 200
    assert client.post(
        "/supplement-items",
        json={"item": "Creatine", "default_dose": "5", "unit": "g", "active": True},
        headers=HEADER,
    ).json()["active"] == "TRUE"
    assert client.post(
        "/context-notes",
        json={"date": "2026-09-22", "text": "travel day", "tags": "travel"},
        headers=HEADER,
    ).status_code == 200
    assert client.post(
        "/media",
        json={"date": "2026-09-22", "pose": "front", "storage_uri": "gs://bucket/a.jpg"},
        headers=HEADER,
    ).status_code == 200
    assert client.get("/exercises", headers=HEADER).status_code == 200


def test_app_source_does_not_import_gemini():
    for path in Path("api/app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "generativeai" not in text
        assert "google.genai" not in text
