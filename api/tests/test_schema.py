from api.app.schema import TABS
from api.app.storage import encode


def test_tabs_and_columns_match_the_spec():
    assert list(TABS) == [
        "Days",
        "Notes",
        "Sessions",
        "Sets",
        "Exercises",
        "Aliases",
        "Nutrition",
        "SupplementItems",
        "Supplements",
        "ContextNotes",
        "Media",
        "DailyView",
    ]
    common = ["id", "created_at", "updated_at", "source"]
    assert TABS["Days"] == common + ["date", "bodyweight_lb", "sleep_hours", "steps", "day_label", "summary"]
    assert TABS["Notes"] == common + [
        "session_date", "day_label", "raw_text", "parse_status", "error_text",
        "model", "prompt_version", "parsed_json", "client_request_id",
    ]
    assert TABS["Sessions"] == common + ["date", "start_time", "end_time", "label", "note_id", "session_notes"]
    assert TABS["Sets"] == common + [
        "session_id", "note_id", "exercise_id", "name_as_written", "set_number",
        "weight_lb", "unit_entered", "reps", "rpe", "set_type", "variation",
        "needs_review", "edited_by_user",
    ]
    assert TABS["Exercises"] == common + [
        "canonical_name", "movement_pattern", "equipment", "primary_muscles",
        "secondary_muscles", "status",
    ]
    assert TABS["Aliases"] == common + ["alias", "exercise_id", "day_label"]
    assert TABS["Nutrition"] == common + ["date", "calories", "protein_g", "carbs_g", "fat_g"]
    assert TABS["SupplementItems"] == common + ["item", "default_dose", "unit", "active"]
    assert TABS["Supplements"] == common + ["date", "item", "dose", "unit"]
    assert TABS["ContextNotes"] == common + ["date", "session_id", "text", "tags"]
    assert TABS["Media"] == common + ["date", "pose", "storage_uri", "taken_at"]
    assert TABS["DailyView"] == [
        "date", "day_label", "bodyweight_lb", "sleep_hours", "steps",
        "calories", "protein_g", "top_lifts", "context", "supplements",
    ]
    assert "id" not in TABS["DailyView"]


def test_encode_zero_bool_and_null():
    assert encode("bodyweight_lb", 0) == "0"
    assert encode("bodyweight_lb", 0.0) == "0"
    assert encode("bodyweight_lb", None) == ""
    assert encode("active", True) == "TRUE"
    assert encode("active", False) == "FALSE"
    assert encode("needs_review", "TRUE") == "TRUE"
    assert encode("canonical_name", "Bench Press") == "Bench Press"
