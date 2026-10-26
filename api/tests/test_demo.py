from datetime import date

from fastapi.testclient import TestClient

from api.app.demo import DEMO_EMAIL, DEMO_PASSWORD, build_demo_book
from api.app.logparse import parse_log
from api.app.main import app
from api.app.trends import build_trends


def test_log_format_keeps_plates_prs_and_bodyweight_reps():
    sessions = parse_log(
        "Summer 2022 Aug 6 Bench 1 plate x 9 "
        "Aug 7 Bench pr 100 2022 School Year "
        "Dec 6 - Push Bench press failed 205, 185 x 3 "
        "May 23 FIRST PULL UP "
        "June 2 Pull up 6, 4 "
        "2025 Apr 27 Bench pr 215"
    )
    loaded = [
        item
        for session in sessions
        for exercise in session["exercises"]
        if exercise["name"] == "Bench Press"
        for item in exercise["sets"]
        if item["weight"]
    ]
    assert any(item["weight"] == 135 and item["reps"] == 9 for item in loaded)
    assert any(item["weight"] == 100 and item["reps"] == 1 for item in loaded)
    assert any(item["weight"] == 215 and item["reps"] == 1 for item in loaded)
    assert all(item["weight"] != 205 for item in loaded)
    pullups = [
        item
        for session in sessions
        for exercise in session["exercises"]
        if exercise["name"] == "Pull Up"
        for item in exercise["sets"]
    ]
    assert pullups
    assert all(item["weight"] is None for item in pullups)


def test_imported_book_uses_the_real_log():
    book = build_demo_book(date(2026, 10, 26))
    trends = build_trends(book)
    benches = [row for row in trends["lifts"] if row["exercise"] == "Bench Press"]
    assert benches[0]["date"].startswith("2022")
    assert benches[0]["top_weight_lb"] == 100
    assert max(row["top_weight_lb"] for row in benches) >= 215
    assert any(row["exercise"] == "Lat Pulldown" for row in trends["lifts"])
    assert any(row["exercise"] == "Incline Dumbbell Press" for row in trends["lifts"])
    assert trends["bodyweight"] == []
    assert book["Notes"][0]["client_request_id"].startswith("lifts-txt-")


def test_reset_restores_the_seed_and_startup_keeps_a_typed_note(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SHEET_ID", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        logged = client.post("/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert logged.status_code == 200
        headers = {"Authorization": f"Bearer {logged.json()['token']}"}
        profile = client.get("/me", headers=headers).json()
        assert profile["name"] == "Ava"
        created = client.post(
            "/notes",
            json={
                "client_request_id": "live",
                "raw_text": "Bench 225x5",
                "session_date": "2026-10-25",
                "day_label": "Push",
                "defer_parse": True,
            },
            headers=headers,
        )
        assert created.status_code == 200
        with TestClient(app) as restarted:
            kept = restarted.get("/notes", headers=headers)
            assert any(row["raw_text"] == "Bench 225x5" for row in kept.json())
        assert client.post("/demo/reset", headers=headers).status_code == 200
        notes = client.get("/notes", headers=headers).json()
        assert len(notes) > 100
        assert all(row["raw_text"] != "Bench 225x5" for row in notes)
        assert notes[0]["client_request_id"].startswith("lifts-txt-")
        other = client.post("/accounts", json={"email": "ada@example.com", "password": "secret"})
        denied = client.post(
            "/demo/reset",
            headers={"Authorization": f"Bearer {other.json()['token']}"},
        )
        assert denied.status_code == 404
    app.dependency_overrides.clear()
