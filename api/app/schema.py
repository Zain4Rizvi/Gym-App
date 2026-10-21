COMMON = ["id", "created_at", "updated_at", "source"]

TABS: dict[str, list[str]] = {
    "Days": COMMON + ["date", "bodyweight_lb", "sleep_hours", "steps", "day_label", "summary"],
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
    "Nutrition": COMMON + ["date", "calories", "protein_g", "carbs_g", "fat_g"],
    "SupplementItems": COMMON + ["item", "default_dose", "unit", "active"],
    "Supplements": COMMON + ["date", "item", "dose", "unit"],
    "ContextNotes": COMMON + ["date", "session_id", "text", "tags"],
    "Media": COMMON + ["date", "pose", "storage_uri", "taken_at"],
    "DailyView": [
        "date", "day_label", "bodyweight_lb", "sleep_hours", "steps",
        "calories", "protein_g", "top_lifts", "context", "supplements",
    ],
}

ROW_TABS = tuple(name for name in TABS if name != "DailyView")
DATE_TABS = frozenset({"Days", "Nutrition"})
BOOL_FIELDS = frozenset({"needs_review", "edited_by_user", "active"})
SET_TYPES = frozenset({"warmup", "working", "drop", "failure"})
DAY_LABELS = frozenset({"Push", "Pull", "Legs", "Other"})
POSES = frozenset({"front", "side", "back"})
SOURCES = frozenset({"gemini", "user", "import"})
PARSE_STATUSES = frozenset({"pending", "done", "error"})
EXERCISE_STATUSES = frozenset({"active", "proposed"})
UNITS = frozenset({"lb", "kg"})
TAGS = frozenset({"sleep", "illness", "stress", "travel"})

PATHS = {
    "Days": "days",
    "Notes": "notes",
    "Sessions": "sessions",
    "Sets": "sets",
    "Exercises": "exercises",
    "Aliases": "aliases",
    "Nutrition": "nutrition",
    "SupplementItems": "supplement-items",
    "Supplements": "supplements",
    "ContextNotes": "context-notes",
    "Media": "media",
}

DATE_FIELDS = {
    "Days": "date",
    "Notes": "session_date",
    "Sessions": "date",
    "Nutrition": "date",
    "Supplements": "date",
    "ContextNotes": "date",
    "Media": "date",
}
