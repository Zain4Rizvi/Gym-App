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


def test_tab_query_is_ignored_on_generated_routes(api):
    client, book = api
    created = client.post(
        "/exercises?tab=Notes",
        json={"canonical_name": "Squat", "status": "active", "primary_muscles": "quads"},
        headers=HEADER,
    )
    body = created.json()
    assert created.status_code == 200
    assert "canonical_name" in body
    assert body["canonical_name"] == "Squat"
    assert "parse_status" not in body
    assert book["Notes"] == []
    assert len(book["Exercises"]) == 1


def test_full_day_log(api):
    client, book = api
    date = "2026-10-21"

    created = client.put(
        f"/days/{date}",
        json={"bodyweight_lb": 180, "sleep_hours": 7.5, "steps": 8000, "summary": "easy day"},
        headers=HEADER,
    )
    assert created.status_code == 200
    day = created.json()
    assert day["date"] == date
    assert day["bodyweight_lb"] == "180"
    assert day["sleep_hours"] == "7.5"
    assert day["steps"] == "8000"
    assert day["summary"] == "easy day"

    corrected = client.put(f"/days/{date}", json={"summary": "still easy"}, headers=HEADER)
    assert corrected.status_code == 200
    assert corrected.json()["id"] == day["id"]
    assert corrected.json()["bodyweight_lb"] == "180"
    assert corrected.json()["sleep_hours"] == "7.5"
    assert corrected.json()["steps"] == "8000"
    assert corrected.json()["summary"] == "still easy"
    assert len(book["Days"]) == 1

    fed = client.put(
        f"/nutrition/{date}",
        json={"calories": 2400, "protein_g": 180, "carbs_g": 220, "fat_g": 70},
        headers=HEADER,
    )
    assert fed.status_code == 200
    totals = fed.json()
    assert totals["calories"] == "2400"
    assert totals["protein_g"] == "180"
    assert totals["carbs_g"] == "220"
    assert totals["fat_g"] == "70"

    refed = client.put(f"/nutrition/{date}", json={"protein_g": 185}, headers=HEADER)
    assert refed.json()["id"] == totals["id"]
    assert refed.json()["calories"] == "2400"
    assert refed.json()["protein_g"] == "185"
    assert refed.json()["carbs_g"] == "220"
    assert refed.json()["fat_g"] == "70"
    assert len(book["Nutrition"]) == 1
    assert "Meals" not in book

    item = client.post(
        "/supplement-items",
        json={"item": "Creatine", "default_dose": 5, "unit": "g", "active": True},
        headers=HEADER,
    )
    assert item.status_code == 200
    assert item.json()["active"] == "TRUE"
    assert item.json()["default_dose"] == "5"

    on = client.post("/supplements/toggle", json={"date": date, "item": "creatine"}, headers=HEADER)
    assert on.status_code == 200
    logged = on.json()
    assert logged["date"] == date
    assert logged["item"] == "Creatine"
    assert logged["dose"] == "5"
    assert logged["unit"] == "g"
    assert logged["source"] == "user"

    off = client.post("/supplements/toggle", json={"date": date, "item": "Creatine"}, headers=HEADER)
    assert off.status_code == 204
    assert book["Supplements"] == []

    again = client.post("/supplements/toggle", json={"date": date, "item": "Creatine"}, headers=HEADER)
    assert again.status_code == 200
    assert again.json()["dose"] == "5"
    assert len(book["Supplements"]) == 1

    assert client.post(
        "/supplements/toggle", json={"date": "21-10-2026", "item": "Creatine"}, headers=HEADER
    ).status_code == 400
    assert client.post(
        "/supplements/toggle", json={"date": date, "item": " "}, headers=HEADER
    ).status_code == 400
    assert client.post(
        "/supplements/toggle", json={"date": date, "item": "Fish oil"}, headers=HEADER
    ).status_code == 404

    note = client.post(
        "/context-notes",
        json={"date": date, "text": "slept short", "tags": "sleep"},
        headers=HEADER,
    )
    assert note.status_code == 200
    assert note.json()["text"] == "slept short"
    assert note.json()["tags"] == "sleep"
    assert note.json()["session_id"] == ""

    view = client.get(f"/daily-view/{date}", headers=HEADER)
    assert view.status_code == 200
    body = view.json()
    assert body["bodyweight_lb"] == "180"
    assert body["sleep_hours"] == "7.5"
    assert body["steps"] == "8000"
    assert body["calories"] == "2400"
    assert body["protein_g"] == "185"
    assert body["context"] == "slept short"
    assert body["supplements"] == "Creatine"

    supplements = client.get("/supplements", params={"date": date}, headers=HEADER)
    assert [row["item"] for row in supplements.json()] == ["Creatine"]
    notes = client.get("/context-notes", params={"date": date}, headers=HEADER)
    assert [row["text"] for row in notes.json()] == ["slept short"]
    saved = client.get(f"/days/{date}", headers=HEADER)
    assert saved.json()["summary"] == "still easy"
    assert client.get(f"/nutrition/{date}", headers=HEADER).json()["fat_g"] == "70"


def test_local_expo_web_origin_is_allowed(api):
    client, _book = api
    response = client.get("/health", headers={"Origin": "http://localhost:8081"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
    preflight = client.options(
        "/notes",
        headers={
            "Origin": "http://127.0.0.1:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:8081"


def test_app_source_does_not_import_gemini():
    for path in Path("api/app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "generativeai" not in text
        assert "google.genai" not in text
