import json
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.main import app, get_book, get_model
from api.app.parse import configured_model, gemini_complete
from api.app.storage import empty_book

HEADER = {"Authorization": "Bearer test-token"}
FIELDS = ("name_as_written", "set_number", "weight_lb", "reps", "unit_entered", "needs_review")


def note_text(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8").removesuffix("\n")


def pairs(sets):
    return [tuple(row[field] for field in FIELDS) for row in sets]


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SHEET_ID", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("live Gemini call")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    book = empty_book()

    def override():
        yield book

    app.dependency_overrides[get_book] = override
    with TestClient(app) as client:
        yield client, book
    app.dependency_overrides.clear()


def seed(client, *names):
    ids = {}
    for name in names:
        response = client.post(
            "/exercises",
            json={"canonical_name": name, "status": "active"},
            headers=HEADER,
        )
        assert response.status_code == 200
        ids[name] = response.json()["id"]
    return ids


def post_note(client, **fields):
    response = client.post("/notes", json=fields, headers=HEADER)
    assert response.status_code == 200
    return response.json()


def test_october_corpus_keeps_typed_lines():
    assert "Pull  up 4" in note_text("2026-10-14-pull.txt")
    assert "Pusjdown 95 x 6, 80 x 8" in note_text("2026-10-20-push.txt")
    assert "140 x i op" in note_text("2026-10-19-pull.txt")
    assert "35 x 6?" in note_text("2026-10-19-pull.txt")
    assert "80 ish" in note_text("2026-10-13-push.txt")
    assert "70 z" in note_text("2026-10-13-push.txt")
    assert "Lat raise machine" in note_text("2026-10-13-push.txt")
    assert note_text("2026-10-10-push.txt").splitlines()[0] == "Oct 10 push"
    assert note_text("2026-10-15-legs.txt").splitlines()[0] == "Oct 15 legs"


def test_oct_10_push_parses_to_one_session(api):
    client, book = api
    seen = []

    def fake(info):
        seen.append(info)
        return {
            "exercises": [
                {"name_as_written": "Incline dumbell", "sets": [
                    {"weight": "75", "reps": "8", "unit": "lb"},
                    {"weight": "75", "reps": "6", "unit": "lb"},
                ]},
                {"name_as_written": "Shoulder press", "sets": [
                    {"weight": "60", "reps": "6"},
                    {"weight": "55", "reps": "8"},
                ]},
                {"name_as_written": "Pushdown", "sets": [{"weight": "85", "reps": ""}]},
            ]
        }

    app.dependency_overrides[get_model] = lambda: fake
    seed(client, "Incline dumbell", "Shoulder press", "Pushdown")
    raw = note_text("2026-10-10-push.txt")
    body = post_note(
        client,
        client_request_id="oct-10",
        raw_text=raw,
        session_date="2026-10-10",
        day_label="Push",
    )
    note = body["note"]
    assert note["parse_status"] == "done"
    assert note["raw_text"] == raw
    assert note["prompt_version"] == "v1"
    assert note["model"] == "gemini-2.5-flash"
    assert note["error_text"] == ""
    assert json.loads(note["parsed_json"])["exercises"][2]["name_as_written"] == "Pushdown"
    assert body["conflicts"] == []
    assert pairs(body["sets"]) == [
        ("Incline dumbell", "1", "75", "8", "lb", "FALSE"),
        ("Incline dumbell", "2", "75", "6", "lb", "FALSE"),
        ("Shoulder press", "1", "60", "6", "lb", "FALSE"),
        ("Shoulder press", "2", "55", "8", "lb", "FALSE"),
        ("Pushdown", "1", "85", "", "lb", "TRUE"),
    ]
    assert all(row["source"] == "gemini" and row["edited_by_user"] == "FALSE" for row in body["sets"])
    assert len(book["Sessions"]) == 1
    session = book["Sessions"][0]
    assert session["date"] == "2026-10-10"
    assert session["label"] == "Push"
    assert session["note_id"] == note["id"]
    assert session["source"] == "gemini"
    assert session["start_time"] == ""
    assert session["end_time"] == ""
    assert session["session_notes"] == ""
    assert len(book["Exercises"]) == 3
    assert set(seen[0]) == {"raw_text", "day_label", "catalog"}
    assert set(seen[0]["catalog"]) == {"exercises", "aliases"}
    again = post_note(client, client_request_id="oct-10", raw_text="nope")
    assert again["note"]["raw_text"] == raw
    assert again["note"]["id"] == note["id"]
    assert len(seen) == 1


def test_oct_15_legs_parses_on_the_parse_route(api):
    client, book = api
    seed(client, "Lat raise", "Leg curl", "Squat", "Rdl", "Calf raise", "Leg extension")
    raw = note_text("2026-10-15-legs.txt")
    created = post_note(
        client,
        client_request_id="oct-15",
        raw_text=raw,
        session_date="2026-10-15",
        day_label="Legs",
    )
    assert created["note"]["parse_status"] == "pending"
    assert created["sets"] == []

    def fake(_info):
        return {
            "exercises": [
                {"name_as_written": "Lat raise", "sets": [
                    {"weight": "110", "reps": "5"}, {"weight": "95", "reps": "8"},
                ]},
                {"name_as_written": "Leg curl", "sets": [
                    {"weight": "205", "reps": "6"}, {"weight": "190", "reps": "8"},
                ]},
                {"name_as_written": "Squat", "sets": [
                    {"weight": "185", "reps": "10"}, {"weight": "185", "reps": "8"},
                ]},
                {"name_as_written": "Rdl", "sets": [
                    {"weight": "205", "reps": "10"}, {"weight": "205", "reps": "8"},
                ]},
                {"name_as_written": "Calf raise", "sets": [
                    {"weight": "290", "reps": "12"}, {"weight": "390", "reps": "10"},
                ]},
                {"name_as_written": "Leg extension", "sets": [
                    {"weight": "265", "reps": "8"}, {"weight": "250", "reps": ""},
                ]},
            ]
        }

    app.dependency_overrides[get_model] = lambda: fake
    parsed = client.post(f"/notes/{created['note']['id']}/parse", headers=HEADER)
    assert parsed.status_code == 200
    body = parsed.json()
    assert body["note"]["parse_status"] == "done"
    assert body["note"]["raw_text"] == raw
    assert body["conflicts"] == []
    assert pairs(body["sets"]) == [
        ("Lat raise", "1", "110", "5", "lb", "FALSE"),
        ("Lat raise", "2", "95", "8", "lb", "FALSE"),
        ("Leg curl", "1", "205", "6", "lb", "FALSE"),
        ("Leg curl", "2", "190", "8", "lb", "FALSE"),
        ("Squat", "1", "185", "10", "lb", "FALSE"),
        ("Squat", "2", "185", "8", "lb", "FALSE"),
        ("Rdl", "1", "205", "10", "lb", "FALSE"),
        ("Rdl", "2", "205", "8", "lb", "FALSE"),
        ("Calf raise", "1", "290", "12", "lb", "FALSE"),
        ("Calf raise", "2", "390", "10", "lb", "FALSE"),
        ("Leg extension", "1", "265", "8", "lb", "FALSE"),
        ("Leg extension", "2", "250", "", "lb", "TRUE"),
    ]
    assert len(book["Sessions"]) == 1
    assert book["Sessions"][0]["date"] == "2026-10-15"
    assert book["Sessions"][0]["label"] == "Legs"
    assert len(book["Exercises"]) == 6
    session_id = book["Sessions"][0]["id"]
    again = client.post(f"/notes/{created['note']['id']}/parse", headers=HEADER)
    assert again.status_code == 200
    assert len(again.json()["sets"]) == 12
    assert len(book["Sessions"]) == 1
    assert book["Sessions"][0]["id"] == session_id


def test_uncertain_tokens_stay_empty_and_flagged(api):
    client, book = api
    seed(client, "Lat raise machine", "Pushdown", "Skull crusher", "Preacher", "Incline dumbell")
    raw = "\n".join([
        "Lat raise machine",
        "Pushdown 80 ish, 80 ish",
        "Skull crusher 80 x 6,70 z",
        "Preacher 155 x 6, 140 x i op",
        "Incline dumbell 40 x 4, 35 x 6?",
        "Pusjdown 95 x 6",
        "Pushdown 85 x",
    ])

    def fake(_info):
        return {
            "exercises": [
                {"name_as_written": "Lat raise machine", "sets": []},
                {"name_as_written": "Pushdown", "sets": [
                    {"weight": "80 ish"},
                    {"weight": "80 ish"},
                    {"weight": "85", "reps": ""},
                ]},
                {"name_as_written": "Skull crusher", "sets": [
                    {"weight": "80", "reps": "6"},
                    {"weight": "70 z"},
                ]},
                {"name_as_written": "Preacher", "sets": [
                    {"weight": "155", "reps": "6"},
                    {"weight": "140", "reps": "i op"},
                ]},
                {"name_as_written": "Incline dumbell", "sets": [
                    {"weight": "40", "reps": "4"},
                    {"weight": "35", "reps": "6?"},
                ]},
                {"name_as_written": "Pusjdown", "sets": [{"weight": "95", "reps": "6"}]},
            ]
        }

    app.dependency_overrides[get_model] = lambda: fake
    created = post_note(
        client,
        client_request_id="messy",
        raw_text=raw,
        session_date="2026-10-21",
        day_label="Other",
    )
    assert pairs(created["sets"]) == [
        ("Lat raise machine", "1", "", "", "", "TRUE"),
        ("Pushdown", "1", "", "", "", "TRUE"),
        ("Pushdown", "2", "", "", "", "TRUE"),
        ("Pushdown", "3", "85", "", "lb", "TRUE"),
        ("Skull crusher", "1", "80", "6", "lb", "FALSE"),
        ("Skull crusher", "2", "", "", "", "TRUE"),
        ("Preacher", "1", "155", "6", "lb", "FALSE"),
        ("Preacher", "2", "140", "", "lb", "TRUE"),
        ("Incline dumbell", "1", "40", "4", "lb", "FALSE"),
        ("Incline dumbell", "2", "35", "", "lb", "TRUE"),
        ("Pusjdown", "1", "95", "6", "lb", "TRUE"),
    ]
    proposed = next(row for row in book["Exercises"] if row["canonical_name"] == "Pusjdown")
    pushdown = next(row for row in book["Exercises"] if row["canonical_name"] == "Pushdown")
    assert proposed["status"] == "proposed"
    assert proposed["source"] == "gemini"
    assert proposed["id"] != pushdown["id"]
    assert created["sets"][-1]["exercise_id"] == proposed["id"]
    assert created["note"]["raw_text"] == raw


def test_kg_zero_rpe_and_amrap(api):
    client, _book = api
    seed(client, "Squat", "Curl")

    def fake(_info):
        return {
            "exercises": [
                {"name_as_written": "Squat", "sets": [
                    {"weight": "20", "reps": "5", "unit": "kg"},
                    {"weight": "0", "reps": "5", "rpe": "@8", "set_type": "warmup"},
                ]},
                {"name_as_written": "Curl", "sets": [{"reps": "AMRAP"}]},
            ]
        }

    app.dependency_overrides[get_model] = lambda: fake
    body = post_note(
        client,
        client_request_id="synthetic-units",
        raw_text="synthetic\nSquat 20 kg x 5\nSquat 0 x 5 @8 warmup\nCurl x AMRAP",
        session_date="2026-01-01",
        day_label="Legs",
    )
    assert [
        (row["name_as_written"], row["set_number"], row["weight_lb"], row["reps"], row["unit_entered"], row["rpe"], row["set_type"], row["needs_review"])
        for row in body["sets"]
    ] == [
        ("Squat", "1", "44.09", "5", "kg", "", "", "FALSE"),
        ("Squat", "2", "0", "5", "lb", "8", "warmup", "FALSE"),
        ("Curl", "1", "", "", "", "", "", "TRUE"),
    ]
    assert body["note"]["raw_text"].startswith("synthetic")


def test_day_scoped_alias_beats_a_blank_alias(api):
    client, book = api
    press = seed(client, "Incline Press")["Incline Press"]
    curl = seed(client, "Incline Curl")["Incline Curl"]
    other = seed(client, "Other Press")["Other Press"]
    for exercise_id, day in ((other, ""), (press, "Push"), (curl, "Pull")):
        created = client.post(
            "/aliases",
            json={"alias": "Incline dumbell", "exercise_id": exercise_id, "day_label": day},
            headers=HEADER,
        )
        assert created.status_code == 200

    def fake(_info):
        return {"exercises": [{"name_as_written": "Incline dumbell", "sets": [{"weight": "40", "reps": "10"}]}]}

    app.dependency_overrides[get_model] = lambda: fake
    pushed = post_note(
        client,
        client_request_id="alias-push",
        raw_text="Incline dumbell 40 x 10",
        session_date="2026-10-10",
        day_label="Push",
    )
    pulled = post_note(
        client,
        client_request_id="alias-pull",
        raw_text="Incline dumbell 40 x 10",
        session_date="2026-10-14",
        day_label="Pull",
    )
    assert pushed["sets"][0]["exercise_id"] == press
    assert pulled["sets"][0]["exercise_id"] == curl
    assert pushed["sets"][0]["needs_review"] == "FALSE"
    assert len(book["Exercises"]) == 3


def test_reparse_keeps_a_user_edit_until_overwrite(api):
    client, book = api
    seed(client, "Bench")
    calls = {"n": 0}

    def fake(_info):
        calls["n"] += 1
        body = {"exercises": [{"name_as_written": "Bench", "sets": [{"weight": "100", "reps": "5"}]}]}
        if calls["n"] > 1:
            body["session_notes"] = "nope"
        return body

    app.dependency_overrides[get_model] = lambda: fake
    created = post_note(
        client,
        client_request_id="edit-me",
        raw_text="Bench 100 x 5",
        session_date="2026-10-10",
        day_label="Push",
    )
    set_id = created["sets"][0]["id"]
    patched = client.patch(f"/sets/{set_id}", json={"weight_lb": 110}, headers=HEADER)
    assert patched.status_code == 200
    assert patched.json()["weight_lb"] == "110"
    assert patched.json()["edited_by_user"] == "TRUE"
    assert book["Aliases"] == []
    saved = created["note"]["parsed_json"]
    conflicted = client.post(f"/notes/{created['note']['id']}/parse", headers=HEADER)
    assert conflicted.status_code == 200
    assert conflicted.json()["conflicts"][0]["set_id"] == set_id
    assert "weight_lb" in conflicted.json()["conflicts"][0]["fields"]
    assert book["Sets"][0]["weight_lb"] == "110"
    assert book["Notes"][0]["parsed_json"] == saved
    assert book["Sessions"][0]["session_notes"] == ""
    replaced = client.post(
        f"/notes/{created['note']['id']}/parse",
        json={"overwrite_set_ids": [set_id]},
        headers=HEADER,
    )
    assert replaced.status_code == 200
    assert replaced.json()["conflicts"] == []
    assert replaced.json()["sets"][0]["weight_lb"] == "100"
    assert replaced.json()["sets"][0]["edited_by_user"] == "FALSE"
    assert replaced.json()["sets"][0]["source"] == "gemini"


def test_assigning_an_exercise_learns_a_day_scoped_alias(api):
    client, book = api

    def fake(_info):
        return {"exercises": [{"name_as_written": "Pusjdown", "sets": [{"weight": "95", "reps": "6"}]}]}

    app.dependency_overrides[get_model] = lambda: fake
    created = post_note(
        client,
        client_request_id="learn",
        raw_text="Pusjdown 95 x 6",
        session_date="2026-10-20",
        day_label="Push",
    )
    pushdown = seed(client, "Pushdown")["Pushdown"]
    set_id = created["sets"][0]["id"]
    assigned = client.patch(f"/sets/{set_id}", json={"exercise_id": pushdown}, headers=HEADER)
    assert assigned.status_code == 200
    assert assigned.json()["edited_by_user"] == "TRUE"
    alias = book["Aliases"][0]
    assert alias["alias"] == "Pusjdown"
    assert alias["exercise_id"] == pushdown
    assert alias["day_label"] == "Push"
    weighed = client.patch(f"/sets/{set_id}", json={"weight_lb": 100}, headers=HEADER)
    assert weighed.status_code == 200
    assert len(book["Aliases"]) == 1


def test_model_failure_keeps_the_typed_note(api):
    client, book = api

    def boom(_info):
        raise RuntimeError("model down")

    app.dependency_overrides[get_model] = lambda: boom
    failed = post_note(
        client,
        client_request_id="retry",
        raw_text="bench 100 x 5",
        session_date="2026-10-10",
        day_label="Push",
    )
    assert failed["note"]["parse_status"] == "error"
    assert failed["note"]["error_text"] == "model down"
    assert failed["note"]["raw_text"] == "bench 100 x 5"
    assert failed["sets"] == []
    assert book["Sessions"] == []
    assert book["Sets"] == []

    def ok(_info):
        return {"exercises": [{"name_as_written": "Bench", "sets": [{"weight": "100", "reps": "5"}]}]}

    app.dependency_overrides[get_model] = lambda: ok
    recovered = post_note(client, client_request_id="retry", raw_text="ignored")
    assert recovered["note"]["parse_status"] == "done"
    assert recovered["note"]["raw_text"] == "bench 100 x 5"
    assert len(recovered["sets"]) == 1


def test_configured_model_is_not_called(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert configured_model() is None
    monkeypatch.setenv("GEMINI_API_KEY", "not-sent")
    assert configured_model() is gemini_complete
