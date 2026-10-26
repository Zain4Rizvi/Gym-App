from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.main import app, get_book
from api.app.storage import empty_book, insert_row

HEADER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def api(monkeypatch, pin):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
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


def test_editing_note_text_drops_generated_sets(api):
    client, book = api
    created = client.post(
        "/notes",
        json={"client_request_id": "req-9", "raw_text": "bench", "session_date": "2026-10-22", "day_label": "Push"},
        headers=HEADER,
    )
    note_id = created.json()["note"]["id"]
    insert_row(book, "Sets", {
        "note_id": note_id, "name_as_written": "Bench", "set_number": "1",
        "weight_lb": 225, "reps": 5, "source": "gemini",
    })
    insert_row(book, "Sets", {
        "note_id": note_id, "name_as_written": "Row", "set_number": "1",
        "weight_lb": 135, "reps": 8, "source": "user", "edited_by_user": True,
    })
    same = client.patch(f"/notes/{note_id}", json={"raw_text": "bench"}, headers=HEADER)
    assert same.json()["raw_text"] == "bench"
    assert len(book["Sets"]) == 2
    changed = client.patch(f"/notes/{note_id}", json={"raw_text": "squat"}, headers=HEADER)
    assert changed.status_code == 200
    assert changed.json()["raw_text"] == "squat"
    assert changed.json()["parse_status"] == "pending"
    assert [row["name_as_written"] for row in book["Sets"]] == ["Row"]
    assert book["Sets"][0]["edited_by_user"] == "TRUE"


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
