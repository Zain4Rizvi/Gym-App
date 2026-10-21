import pytest

from api.app.storage import Book, Duplicate, Missing, delete_row, empty_book, get_row, insert_row, patch_row


def test_insert_patch_null_and_ignore_unknown_field():
    book = empty_book()
    row = insert_row(book, "Exercises", {"canonical_name": "Bench Press", "status": "active", "nope": "x"})
    assert row["id"]
    assert row["source"] == "user"
    assert row["created_at"].endswith("Z")
    assert "nope" not in row
    assert row["equipment"] == ""
    patched = patch_row(book, "Exercises", row["id"], {"equipment": "barbell", "movement_pattern": None})
    assert patched["canonical_name"] == "Bench Press"
    assert patched["equipment"] == "barbell"
    assert patched["movement_pattern"] == ""
    assert get_row(book, "Exercises", row["id"])["equipment"] == "barbell"


def test_unique_keys_and_bool_storage():
    book = empty_book()
    insert_row(book, "Exercises", {"canonical_name": "Bench Press", "status": "active"})
    with pytest.raises(Duplicate):
        insert_row(book, "Exercises", {"canonical_name": "bench press", "status": "active"})
    insert_row(book, "Aliases", {"alias": "Incline Dumbell", "day_label": "Push", "exercise_id": "e1"})
    insert_row(book, "Aliases", {"alias": "Incline Dumbell", "day_label": "Pull", "exercise_id": "e2"})
    with pytest.raises(Duplicate):
        insert_row(book, "Aliases", {"alias": "incline dumbell", "day_label": "Push", "exercise_id": "e3"})
    item = insert_row(book, "SupplementItems", {"item": "Creatine", "active": True})
    assert item["active"] == "TRUE"
    with pytest.raises(Duplicate):
        insert_row(book, "SupplementItems", {"item": "creatine", "active": True})
    insert_row(book, "Supplements", {"date": "2026-09-22", "item": "Creatine", "dose": "5"})
    with pytest.raises(Duplicate):
        insert_row(book, "Supplements", {"date": "2026-09-22", "item": "creatine", "dose": "5"})


def test_bad_enum_rejected_and_delete_keeps_the_note():
    book = empty_book()
    with pytest.raises(ValueError):
        insert_row(book, "Sets", {"set_type": "cardio"})
    with pytest.raises(ValueError):
        insert_row(book, "ContextNotes", {"date": "2026-09-22", "tags": "sleep,hungry"})
    note = insert_row(book, "Notes", {"client_request_id": "req-1", "raw_text": "bench", "parse_status": "done"})
    assert note["parse_status"] == "pending"
    again = insert_row(book, "Notes", {"client_request_id": "req-1", "raw_text": "other"})
    assert again["id"] == note["id"]
    assert again["raw_text"] == "bench"
    assert len(book["Notes"]) == 1
    workout = insert_row(book, "Sets", {"note_id": note["id"], "set_number": "1", "weight_lb": 225})
    delete_row(book, "Sets", workout["id"])
    assert book["Sets"] == []
    assert book["Notes"][0]["id"] == note["id"]
    with pytest.raises(Missing):
        get_row(book, "Sets", workout["id"])


def test_duplicate_patch_does_not_keep_the_edit():
    book = empty_book()
    first = insert_row(book, "Exercises", {"canonical_name": "Squat", "status": "active"})
    second = insert_row(book, "Exercises", {"canonical_name": "Deadlift", "status": "active"})
    with pytest.raises(Duplicate):
        patch_row(book, "Exercises", second["id"], {"canonical_name": "squat"})
    assert get_row(book, "Exercises", second["id"])["canonical_name"] == "Deadlift"
    assert isinstance(book, Book)
    assert book.dirty is True


from api.app.storage import upsert_by_date


def test_date_upsert_is_partial_and_kg_converts_once():
    book = empty_book()
    first = upsert_by_date(book, "Days", "2026-09-22", {"bodyweight_lb": 0, "day_label": "Push"})
    assert first["bodyweight_lb"] == "0"
    second = upsert_by_date(book, "Days", "2026-09-22", {"sleep_hours": 7, "day_label": None})
    assert second["id"] == first["id"]
    assert second["bodyweight_lb"] == "0"
    assert second["sleep_hours"] == "7"
    assert second["day_label"] == ""
    assert len(book["Days"]) == 1

    lifted = insert_row(book, "Sets", {"weight_lb": 20, "unit_entered": "kg", "set_number": "1"})
    assert lifted["weight_lb"] == "44.09"
    assert lifted["unit_entered"] == "kg"
    patched = patch_row(book, "Sets", lifted["id"], {"reps": "5"})
    assert patched["weight_lb"] == "44.09"
    pounds = insert_row(book, "Sets", {"weight_lb": 225, "set_number": "1"})
    assert pounds["weight_lb"] == "225"
    assert pounds["unit_entered"] == "lb"


def test_daily_view_joins_the_day_and_picks_the_top_set():
    book = empty_book()
    upsert_by_date(book, "Days", "2026-09-22", {"bodyweight_lb": 180, "sleep_hours": 8, "steps": 9000})
    upsert_by_date(book, "Nutrition", "2026-09-22", {"calories": 2800, "protein_g": 190})
    push = insert_row(book, "Sessions", {"date": "2026-09-22", "label": "Push"})
    pull = insert_row(book, "Sessions", {"date": "2026-09-22", "label": "Pull"})
    bench = insert_row(book, "Exercises", {"canonical_name": "Bench Press", "status": "active"})
    insert_row(book, "Sets", {
        "session_id": push["id"], "exercise_id": bench["id"], "name_as_written": "bench",
        "set_number": "1", "set_type": "warmup", "weight_lb": 45, "reps": 10,
    })
    insert_row(book, "Sets", {
        "session_id": push["id"], "exercise_id": bench["id"], "name_as_written": "bench",
        "set_number": "2", "set_type": "working", "weight_lb": 225, "reps": 5,
    })
    insert_row(book, "Sets", {
        "session_id": push["id"], "exercise_id": bench["id"], "name_as_written": "bench",
        "set_number": "3", "set_type": "working", "weight_lb": 225, "reps": 3,
    })
    insert_row(book, "Sets", {
        "session_id": pull["id"], "name_as_written": "Row",
        "set_number": "1", "set_type": "working", "weight_lb": 135, "reps": 8,
    })
    insert_row(book, "ContextNotes", {"date": "2026-09-22", "text": "slept well", "tags": "sleep"})
    insert_row(book, "Supplements", {"date": "2026-09-22", "item": "Creatine", "dose": "5", "unit": "g"})
    view = book["DailyView"]
    assert len(view) == 1
    assert view[0]["day_label"] == "Push, Pull"
    assert view[0]["bodyweight_lb"] == "180"
    assert view[0]["calories"] == "2800"
    assert view[0]["protein_g"] == "190"
    assert view[0]["top_lifts"] == "Bench Press 225x5; Row 135x8"
    assert view[0]["context"] == "slept well"
    assert view[0]["supplements"] == "Creatine"
    delete_row(book, "Days", book["Days"][0]["id"])
    assert book["DailyView"][0]["bodyweight_lb"] == ""
    assert book["DailyView"][0]["day_label"] == "Push, Pull"
