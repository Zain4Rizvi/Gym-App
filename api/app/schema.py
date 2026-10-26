COMMON = ["id", "created_at", "updated_at", "source"]

TABS: dict[str, list[str]] = {
    "Notes": COMMON + [
        "session_date", "day_label", "raw_text", "parse_status", "error_text",
        "model", "prompt_version", "parsed_json", "client_request_id",
    ],
    "Sessions": COMMON + ["date", "start_time", "end_time", "label", "note_id", "session_notes"],
    "Sets": COMMON + [
        "session_id", "note_id", "exercise_id", "name_as_written", "set_number",
        "weight_lb", "unit_entered", "reps", "rpe", "set_type", "variation",
        "needs_review", "edited_by_user",
    ],
    "Exercises": COMMON + [
        "canonical_name", "movement_pattern", "equipment", "primary_muscles",
        "secondary_muscles", "status",
    ],
    "Aliases": COMMON + ["alias", "exercise_id", "day_label"],
}

BOOL_FIELDS = frozenset({"needs_review", "edited_by_user"})
SET_TYPES = frozenset({"warmup", "working", "drop", "failure"})
DAY_LABELS = frozenset({"Push", "Pull", "Legs", "Other"})
SOURCES = frozenset({"gemini", "user", "import"})
PARSE_STATUSES = frozenset({"pending", "done", "error"})
EXERCISE_STATUSES = frozenset({"active", "proposed"})
UNITS = frozenset({"lb", "kg"})
