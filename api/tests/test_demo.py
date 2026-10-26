from datetime import date

from fastapi.testclient import TestClient

from api.app.demo import DEMO_EMAIL, DEMO_PASSWORD, SLEEP_NOTE, block, build_demo_book
from api.app.main import app
from api.app.trends import build_trends


def test_seed_stalls_bench_and_keeps_the_sleep_note():
    today = date(2026, 10, 25)
    book = build_demo_book(today)
    trends = build_trends(book)
    start, _end = block(today)

    benches = [row for row in trends["lifts"] if row["exercise"] == "Bench Press"]
    assert len(benches) == 8
    assert benches[3]["epley"] == benches[4]["epley"]
    assert benches[0]["top_weight_lb"] == 185
    assert benches[7]["top_weight_lb"] == 205
    assert benches[7]["epley"] > benches[0]["epley"]

    squats = [row for row in trends["lifts"] if row["exercise"] == "Back Squat"]
    assert squats[0]["top_weight_lb"] == 275
    assert squats[7]["top_weight_lb"] == 315
    assert squats[4]["epley"] > squats[3]["epley"]

    deadlifts = [row for row in trends["lifts"] if row["exercise"] == "Deadlift"]
    assert deadlifts[0]["top_weight_lb"] == 365
    assert deadlifts[7]["top_weight_lb"] == 405

    weights = trends["bodyweight"]
    assert weights[0]["bodyweight_lb"] == 186.4
    assert weights[-1]["bodyweight_lb"] == 181.2

    note = next(row for row in book["ContextNotes"] if row["text"] == SLEEP_NOTE)
    assert "sleep" in note["tags"] and "travel" in note["tags"]
    assert (date.fromisoformat(note["date"]) - start).days // 7 == 4
    assert not any(row["date"] == note["date"] and row["item"] == "Creatine" for row in book["Supplements"])
    assert any(row["date"] == start.isoformat() and row["item"] == "Creatine" for row in book["Supplements"])
    protein = next(row for row in book["Nutrition"] if row["date"] == note["date"])
    assert protein["protein_g"] == "140"
    assert protein["calories"] == "1900"
    assert book["Media"] == []


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
        assert profile["height_in"] == 68
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
        assert created.json()["note"]["parse_status"] == "pending"
        with TestClient(app) as restarted:
            kept = restarted.get("/notes", headers=headers)
            assert any(row["raw_text"] == "Bench 225x5" for row in kept.json())
        assert client.post("/demo/reset", headers=headers).status_code == 200
        notes = client.get("/notes", headers=headers).json()
        assert len(notes) == 24
        assert all(row["raw_text"] != "Bench 225x5" for row in notes)
        other = client.post("/accounts", json={"email": "ada@example.com", "password": "secret"})
        denied = client.post(
            "/demo/reset",
            headers={"Authorization": f"Bearer {other.json()['token']}"},
        )
        assert denied.status_code == 404
    app.dependency_overrides.clear()
