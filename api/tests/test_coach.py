import json
import urllib.request

import pytest
from fastapi.testclient import TestClient

from api.app.coach import complete_chat, log_text
from api.app.main import app, get_book
from api.app.storage import empty_book

HEADER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.delenv("SHEET_ID", raising=False)
    book = empty_book()

    def override():
        yield book

    app.dependency_overrides[get_book] = override
    with TestClient(app) as client:
        yield client, book
    app.dependency_overrides.clear()


def test_coach_needs_a_model_and_a_question(api):
    client, book = api
    closed = client.post("/coach", json={"messages": [{"role": "user", "content": "hi"}]})
    assert closed.status_code == 401
    missing = client.post("/coach", json={}, headers=HEADER)
    assert missing.status_code == 400
    unconfigured = client.post(
        "/coach",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=HEADER,
    )
    assert unconfigured.status_code == 503
    assert unconfigured.json()["detail"] == "coach not configured"
    assert book.dirty is False


def test_coach_sends_the_log_and_skips_photos(api, monkeypatch):
    client, book = api
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    book["Sets"].append({"id": "set-1", "name_as_written": "Bench Press", "weight_lb": "225", "reps": "5"})
    book["Nutrition"].append({"date": "2026-10-25", "calories": "2400", "protein_g": "180"})
    book["Media"].append({"id": "photo-1", "pose": "front", "storage_uri": "data/photos/secret.jpg"})
    seen = {}

    class Response:
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "Add a rep on bench."}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_open(request, timeout=0):
        seen["body"] = json.loads(request.data.decode())
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    before = {name: list(rows) for name, rows in book.items()}
    reply = client.post(
        "/coach",
        json={"messages": [{"role": "user", "content": "What should I do on bench?"}]},
        headers=HEADER,
    )
    assert reply.status_code == 200
    assert reply.json() == {"reply": "Add a rep on bench."}
    system = seen["body"]["messages"][0]["content"]
    assert "Bench Press" in system
    assert "225" in system
    assert "180" in system
    assert "secret.jpg" not in system
    assert "storage_uri" not in system
    assert "response_format" not in seen["body"]
    assert seen["timeout"] == 60
    assert {name: list(rows) for name, rows in book.items()} == before


def test_gemini_coach_asks_for_text(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    seen = {}

    class Response:
        def read(self):
            return json.dumps({
                "candidates": [{"content": {"parts": [{"text": "Rest tomorrow."}]}}],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_open(request, timeout=0):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data.decode())
        seen["headers"] = {key.lower(): value for key, value in request.header_items()}
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    text = complete_chat(
        "system text",
        [{"role": "assistant", "content": "Noted."}, {"role": "user", "content": "Should I bench?"}],
    )
    assert text == "Rest tomorrow."
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert "responseMimeType" not in seen["body"]
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "system text"
    assert [item["role"] for item in seen["body"]["contents"]] == ["model", "user"]
    assert seen["headers"]["x-goog-api-key"] == "gem-key"


def test_coach_log_keeps_the_newest_rows_when_the_book_is_huge():
    book = empty_book()
    book["Sessions"].append({"id": "session", "date": "2026-01-01", "label": "Push"})
    for number in range(500):
        book["Sets"].append({
            "id": str(number),
            "session_id": "session",
            "name_as_written": f"Move{number}",
            "weight_lb": "100",
            "reps": "5",
            "set_number": "1",
        })
    text = log_text(book)
    assert "left out" in text
    assert "Move499" in text
    assert "Move0" not in text
    assert len(text) <= 10080
