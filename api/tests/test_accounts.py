import pytest
from fastapi.testclient import TestClient

from api.app.main import app
from api.app.storage import Duplicate, register_account


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client, tmp_path
    app.dependency_overrides.clear()


def test_two_accounts_cannot_read_each_others_notes(local):
    client, tmp_path = local
    first = register_account("one@example.com", "secret")
    second = register_account("two@example.com", "secret")
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
    created = register_account("ada@example.com", "secret")
    with pytest.raises(Duplicate):
        register_account("Ada@example.com", "other")

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
    created = register_account("ada@example.com", "secret")
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
    created = register_account("ada@example.com", "secret")
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
