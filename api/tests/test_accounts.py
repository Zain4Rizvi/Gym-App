import pytest
from fastapi.testclient import TestClient

from api.app.main import app

HEADER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SHEET_ID", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client, tmp_path
    app.dependency_overrides.clear()


def _account(client, email, password="secret"):
    created = client.post("/accounts", json={"email": email, "password": password})
    assert created.status_code == 200
    body = created.json()
    assert body["email"] == email
    assert body["token"]
    return body


def test_two_accounts_cannot_read_each_others_notes(local):
    client, tmp_path = local
    first = _account(client, "one@example.com")
    second = _account(client, "two@example.com")
    headers_one = {"Authorization": f"Bearer {first['token']}"}
    headers_two = {"Authorization": f"Bearer {second['token']}"}

    saved = client.post(
        "/notes",
        json={"client_request_id": "n1", "raw_text": "bench 225", "session_date": "2026-10-21", "day_label": "Push"},
        headers=headers_one,
    )
    assert saved.status_code == 200

    assert client.get("/notes", headers=headers_two).json() == []
    listed = client.get("/notes", headers=headers_one).json()
    assert len(listed) == 1
    assert listed[0]["raw_text"] == "bench 225"

    accounts = (tmp_path / "accounts.json").read_text(encoding="utf-8")
    assert "secret" not in accounts
    assert first["token"] not in accounts
    assert second["token"] not in accounts
    books = list((tmp_path / "books").glob("*.json"))
    user_books = [book for book in books if "bench 225" in book.read_text(encoding="utf-8")]
    assert len(user_books) == 1


def test_duplicate_email_is_conflict_and_login_returns_a_token(local):
    client, _tmp_path = local
    created = _account(client, "ada@example.com")
    again = client.post("/accounts", json={"email": "Ada@example.com", "password": "other"})
    assert again.status_code == 409

    logged = client.post("/login", json={"email": "ada@example.com", "password": "secret"})
    assert logged.status_code == 200
    body = logged.json()
    assert body["email"] == "ada@example.com"
    assert body["token"] != created["token"]
    assert client.get("/me", headers={"Authorization": f"Bearer {body['token']}"}).json() == {
        "email": "ada@example.com",
        "name": "",
        "height_in": None,
        "split": {
            "Mon": "Push",
            "Tue": "Pull",
            "Wed": "Legs",
            "Thu": "Push",
            "Fri": "Pull",
            "Sat": "Legs",
            "Sun": "",
        },
    }
    assert client.post("/login", json={"email": "ada@example.com", "password": "nope"}).status_code == 401
    assert client.get("/me").status_code == 401
    assert client.get("/notes").status_code == 401


def test_profile_height_and_split(local):
    client, _tmp_path = local
    created = _account(client, "ada@example.com")
    headers = {"Authorization": f"Bearer {created['token']}"}

    updated = client.patch(
        "/me",
        headers=headers,
        json={"height_in": 70, "split": {"Mon": "Pull", "Sun": "Rest"}},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["height_in"] == 70
    assert body["split"]["Mon"] == "Pull"
    assert body["split"]["Tue"] == "Pull"
    assert body["split"]["Sun"] == ""

    again = client.get("/me", headers=headers)
    assert again.json()["height_in"] == 70
    assert again.json()["split"]["Mon"] == "Pull"
    assert client.patch("/me", headers=headers, json={"split": {"Mon": "Chest"}}).status_code == 400
    assert client.patch("/me", headers=headers, json={"height_in": -1}).status_code == 400


def test_local_book_survives_a_new_load(local):
    client, _tmp_path = local
    created = _account(client, "ada@example.com")
    headers = {"Authorization": f"Bearer {created['token']}"}
    saved = client.post(
        "/notes",
        json={"client_request_id": "keep", "raw_text": "squat", "session_date": "2026-10-21", "day_label": "Legs"},
        headers=headers,
    )
    assert saved.status_code == 200
    note_id = saved.json()["note"]["id"]

    with TestClient(app) as restarted:
        listed = restarted.get("/notes", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == note_id
    assert listed.json()[0]["raw_text"] == "squat"


def test_shared_token_uses_one_local_book_when_sheet_id_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.delenv("SHEET_ID", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        saved = client.post(
            "/notes",
            json={"client_request_id": "shared", "raw_text": "row"},
            headers=HEADER,
        )
        assert saved.status_code == 200
        created = client.post("/accounts", json={"email": "ada@example.com", "password": "secret"})
        assert created.status_code == 200
        user_headers = {"Authorization": f"Bearer {created.json()['token']}"}
        assert client.get("/notes", headers=user_headers).json() == []
        assert client.get("/notes", headers=HEADER).json()[0]["raw_text"] == "row"
    with TestClient(app) as restarted:
        assert restarted.get("/notes", headers=HEADER).json()[0]["raw_text"] == "row"
    app.dependency_overrides.clear()


def test_sheet_mode_stays_one_sheet_and_one_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHEET_ID", "sheet-1")
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app.dependency_overrides.clear()
    calls = {}

    def fake_service():
        return "service"

    def fake_load(service, sheet_id):
        calls["load"] = (service, sheet_id)
        from api.app.storage import empty_book

        return empty_book()

    def fake_save(service, sheet_id, book):
        calls["save"] = (service, sheet_id, book["Notes"][0]["raw_text"])

    monkeypatch.setattr("api.app.main.sheets_service", fake_service)
    monkeypatch.setattr("api.app.main.load_book", fake_load)
    monkeypatch.setattr("api.app.main.save_book", fake_save)

    with TestClient(app) as client:
        created = client.post("/accounts", json={"email": "ada@example.com", "password": "secret"})
        assert created.status_code == 200
        user_headers = {"Authorization": f"Bearer {created.json()['token']}"}
        assert client.get("/notes", headers=user_headers).status_code == 401
        saved = client.post(
            "/notes",
            json={"client_request_id": "sheet", "raw_text": "deadlift"},
            headers=HEADER,
        )
        assert saved.status_code == 200
    assert calls["load"] == ("service", "sheet-1")
    assert calls["save"][0] == "service"
    assert calls["save"][1] == "sheet-1"
    assert calls["save"][2] == "deadlift"
    app.dependency_overrides.clear()
