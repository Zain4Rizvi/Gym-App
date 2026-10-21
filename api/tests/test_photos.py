from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

MARKER = b"GYM_PHOTO_BYTES_MARKER_9f3a"


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


def _signup(client, email):
    created = client.post("/accounts", json={"email": email, "password": "secret"})
    assert created.status_code == 200
    return {"Authorization": f"Bearer {created.json()['token']}"}


def test_photo_bytes_stay_out_of_the_book_and_the_other_account(local):
    client, tmp_path = local
    owner = _signup(client, "owner@example.com")
    other = _signup(client, "other@example.com")
    uploaded = client.post(
        "/media",
        data={"date": "2026-10-21", "pose": "front"},
        files={"file": ("../../outside.jpg", MARKER, "image/jpeg")},
        headers=owner,
    )
    assert uploaded.status_code == 200
    row = uploaded.json()
    assert row["pose"] == "front"
    assert row["date"] == "2026-10-21"
    assert MARKER.decode() not in row["storage_uri"]
    assert ".." not in row["storage_uri"]

    fetched = client.get(f"/media/{row['id']}/file", headers=owner)
    assert fetched.status_code == 200
    assert fetched.content == MARKER
    assert client.get(f"/media/{row['id']}/file", headers=other).status_code == 404

    books = list((tmp_path / "books").glob("*.json"))
    assert books
    for book in books:
        assert MARKER not in book.read_bytes()
    assert not (tmp_path / "outside.jpg").exists()
    stored = [path for path in (tmp_path / "photos").rglob("*") if path.is_file()]
    assert len(stored) == 1
    assert stored[0].read_bytes() == MARKER
    assert tmp_path.resolve() in stored[0].resolve().parents


def test_media_file_rejects_a_path_outside_the_book(local):
    client, tmp_path = local
    owner = _signup(client, "owner@example.com")
    secret = tmp_path / "accounts.json"
    assert b"owner@example.com" in secret.read_bytes()
    uploaded = client.post(
        "/media",
        data={"date": "2026-10-21", "pose": "back"},
        files={"file": ("pic.jpg", MARKER, "image/jpeg")},
        headers=owner,
    )
    assert uploaded.status_code == 200
    assert client.get(f"/media/{uploaded.json()['id']}/file", headers=owner).content == MARKER
    created = client.post(
        "/media",
        json={"date": "2026-10-21", "pose": "side", "storage_uri": "../accounts.json"},
        headers=owner,
    )
    assert created.status_code == 200
    fetched = client.get(f"/media/{created.json()['id']}/file", headers=owner)
    assert fetched.status_code == 404
    assert b"owner@example.com" not in fetched.content


def test_photos_module_does_not_import_gemini_parse_or_urllib():
    text = Path("api/app/photos.py").read_text(encoding="utf-8").lower()
    assert "gemini" not in text
    assert "urllib" not in text
    assert "parse" not in text
