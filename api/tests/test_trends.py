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


def test_225_for_5_is_epley_262_5(api):
    client, book = api
    empty = client.get("/trends", headers=HEADER)
    assert empty.status_code == 200
    assert empty.json()["lifts"] == []

    exercise = client.post(
        "/exercises",
        json={"canonical_name": "Bench Press", "primary_muscles": "chest, triceps", "status": "active"},
        headers=HEADER,
    ).json()
    session = client.post(
        "/sessions",
        json={"date": "2026-10-21", "label": "Push"},
        headers=HEADER,
    ).json()
    client.post(
        "/sets",
        json={
            "session_id": session["id"],
            "exercise_id": exercise["id"],
            "name_as_written": "Bench",
            "set_number": "1",
            "weight_lb": 300,
            "reps": 5,
            "set_type": "warmup",
        },
        headers=HEADER,
    )
    client.post(
        "/sets",
        json={
            "session_id": session["id"],
            "exercise_id": exercise["id"],
            "name_as_written": "Bench",
            "set_number": "2",
            "weight_lb": 225,
            "reps": 5,
            "set_type": "working",
        },
        headers=HEADER,
    )
    client.put("/days/2026-10-20", json={"bodyweight_lb": 178}, headers=HEADER)
    client.put("/days/2026-10-21", json={"bodyweight_lb": 180}, headers=HEADER)
    client.put("/nutrition/2026-10-21", json={"calories": 2400, "protein_g": 180}, headers=HEADER)
    client.post(
        "/supplement-items",
        json={"item": "Creatine", "default_dose": 5, "unit": "g", "active": True},
        headers=HEADER,
    )
    client.post("/supplements/toggle", json={"date": "2026-10-21", "item": "Creatine"}, headers=HEADER)

    response = client.get("/trends", headers=HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["lifts"] == [
        {
            "exercise": "Bench Press",
            "date": "2026-10-21",
            "label": "Push",
            "top_weight_lb": 225,
            "epley": 262.5,
        }
    ]
    assert body["bodyweight"] == [
        {"date": "2026-10-20", "bodyweight_lb": 178, "mean_7d": 178},
        {"date": "2026-10-21", "bodyweight_lb": 180, "mean_7d": 179},
    ]
    assert body["nutrition"] == [{"date": "2026-10-21", "calories": 2400, "protein_g": 180}]
    assert body["adherence"] == {"supplement_dates": 1, "day_dates": 2, "ratio": 0.5}
    assert body["muscles"] == [
        {"muscle": "chest", "week": "2026-10-19", "volume": 1125},
        {"muscle": "triceps", "week": "2026-10-19", "volume": 1125},
    ]
    assert all("epley" not in row and "1rm" not in row for row in book["Sets"])
