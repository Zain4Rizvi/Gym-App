import pytest
from fastapi.testclient import TestClient

from api.app.main import app, get_book
from api.app.storage import empty_book, insert_row

HEADER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def api(pin):
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
    assert empty.json()["adherence"] == {"supplement_dates": 0, "day_dates": 0, "ratio": None}

    exercise = insert_row(book, "Exercises", {"canonical_name": "Bench Press", "status": "active"})
    session = insert_row(book, "Sessions", {"date": "2026-10-21", "label": "Push"})
    insert_row(book, "Sets", {
        "session_id": session["id"],
        "exercise_id": exercise["id"],
        "name_as_written": "Bench",
        "set_number": "1",
        "weight_lb": 300,
        "reps": 5,
        "set_type": "warmup",
    })
    insert_row(book, "Sets", {
        "session_id": session["id"],
        "exercise_id": exercise["id"],
        "name_as_written": "Bench",
        "set_number": "2",
        "weight_lb": 225,
        "reps": 5,
        "set_type": "working",
    })

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
    assert body["bodyweight"] == []
    assert body["nutrition"] == []
    assert body["adherence"] == {"supplement_dates": 0, "day_dates": 1, "ratio": 0.0}
    assert "muscles" not in body
    assert all("epley" not in row and "1rm" not in row for row in book["Sets"])
