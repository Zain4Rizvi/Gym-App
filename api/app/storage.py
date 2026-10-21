import uuid
from datetime import datetime, timezone

from api.app.schema import (
    BOOL_FIELDS,
    DATE_FIELDS,
    DATE_TABS,
    DAY_LABELS,
    EXERCISE_STATUSES,
    PARSE_STATUSES,
    POSES,
    ROW_TABS,
    SET_TYPES,
    SOURCES,
    TAGS,
    TABS,
    UNITS,
)

LB_PER_KG = 2.2046226218


class Book(dict):
    def __init__(self):
        super().__init__((name, []) for name in TABS)
        self.dirty = False
        self.headers: dict[str, list[str]] = {}


def empty_book() -> Book:
    return Book()


def encode(field: str, value) -> str:
    if value is None:
        return ""
    if field in BOOL_FIELDS or isinstance(value, bool):
        if value is True or value == "TRUE":
            return "TRUE"
        if value is False or value == "FALSE":
            return "FALSE"
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return format(value, "g")
    return str(value)


class Duplicate(Exception):
    def __init__(self, tab: str):
        self.tab = tab
        super().__init__(tab)


class Missing(Exception):
    def __init__(self, tab: str, row_id: str):
        self.tab = tab
        self.row_id = row_id
        super().__init__(row_id)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_fields(tab: str, fields: dict) -> None:
    bad: list[str] = []
    checks = {
        "set_type": SET_TYPES,
        "day_label": DAY_LABELS,
        "pose": POSES,
        "source": SOURCES,
        "parse_status": PARSE_STATUSES,
        "unit_entered": UNITS,
    }
    for key, allowed in checks.items():
        value = fields.get(key)
        if value is None or value == "":
            continue
        if str(value) not in allowed:
            bad.append(key)
    if tab == "Exercises":
        status = fields.get("status")
        if status not in (None, "") and str(status) not in EXERCISE_STATUSES:
            bad.append("status")
    tags = fields.get("tags")
    if tags not in (None, ""):
        parts = [part.strip() for part in str(tags).split(",") if part.strip()]
        if any(part not in TAGS for part in parts):
            bad.append("tags")
    if bad:
        raise ValueError(", ".join(bad))


def canonicalize_weight(row: dict[str, str], fields: dict) -> None:
    if "weight_lb" not in fields or fields["weight_lb"] is None or fields["weight_lb"] == "":
        return
    unit = fields.get("unit_entered", row.get("unit_entered", ""))
    if unit == "kg":
        row["weight_lb"] = f"{round(float(fields['weight_lb']) * LB_PER_KG, 2):.2f}"
        row["unit_entered"] = "kg"
    elif unit in ("", "lb"):
        row["unit_entered"] = "lb"


def apply_fields(tab: str, row: dict[str, str], fields: dict) -> None:
    validate_fields(tab, fields)
    allowed = set(TABS[tab]) - {"id", "created_at"}
    for key, value in fields.items():
        if key not in allowed:
            continue
        row[key] = "" if value is None else encode(key, value)
    if tab == "Sets":
        canonicalize_weight(row, fields)


def duplicate(book: Book, tab: str, row: dict[str, str], ignore_id: str | None = None) -> bool:
    others = [item for item in book[tab] if item["id"] != ignore_id]
    if tab in ("Days", "Nutrition"):
        return row["date"] != "" and any(item["date"] == row["date"] for item in others)
    if tab == "Supplements":
        if row["date"] == "" or row["item"] == "":
            return False
        return any(
            item["date"] == row["date"] and item["item"].casefold() == row["item"].casefold()
            for item in others
        )
    if tab == "Aliases":
        if row["alias"] == "":
            return False
        return any(
            item["alias"].casefold() == row["alias"].casefold() and item["day_label"] == row["day_label"]
            for item in others
        )
    if tab == "Notes":
        if row["client_request_id"] == "":
            return False
        return any(item["client_request_id"] == row["client_request_id"] for item in others)
    if tab == "Exercises":
        if row["canonical_name"] == "":
            return False
        return any(item["canonical_name"].casefold() == row["canonical_name"].casefold() for item in others)
    if tab == "SupplementItems":
        if row["item"] == "":
            return False
        return any(item["item"].casefold() == row["item"].casefold() for item in others)
    return False


def insert_row(book: Book, tab: str, fields: dict) -> dict[str, str]:
    if tab not in ROW_TABS:
        raise ValueError(tab)
    request_id = str(fields.get("client_request_id") or "")
    if tab == "Notes" and request_id:
        existing = next((row for row in book["Notes"] if row["client_request_id"] == request_id), None)
        if existing:
            return existing
    row = {header: "" for header in TABS[tab]}
    now = utc_now()
    row["id"] = str(uuid.uuid4())
    row["created_at"] = now
    row["updated_at"] = now
    row["source"] = "user"
    apply_fields(tab, row, fields)
    if tab == "Notes":
        row["parse_status"] = "pending"
    if duplicate(book, tab, row):
        raise Duplicate(tab)
    book[tab].append(row)
    rebuild_daily_view(book)
    book.dirty = True
    return row


def get_row(book: Book, tab: str, row_id: str) -> dict[str, str]:
    if tab not in TABS:
        raise ValueError(tab)
    found = next((row for row in book[tab] if row.get("id") == row_id), None)
    if found is None:
        raise Missing(tab, row_id)
    return found


def patch_row(book: Book, tab: str, row_id: str, fields: dict) -> dict[str, str]:
    if tab not in ROW_TABS:
        raise ValueError(tab)
    row = get_row(book, tab, row_id)
    trial = dict(row)
    apply_fields(tab, trial, fields)
    trial["updated_at"] = utc_now()
    if duplicate(book, tab, trial, ignore_id=row_id):
        raise Duplicate(tab)
    row.clear()
    row.update(trial)
    rebuild_daily_view(book)
    book.dirty = True
    return row


def delete_row(book: Book, tab: str, row_id: str) -> None:
    if tab not in ROW_TABS:
        raise ValueError(tab)
    row = get_row(book, tab, row_id)
    book[tab].remove(row)
    rebuild_daily_view(book)
    book.dirty = True


def rows_by_field(book: Book, tab: str, field: str, value: str) -> list[dict[str, str]]:
    return [row for row in book[tab] if row.get(field) == value]


def sets_on_date(book: Book, date: str) -> list[dict[str, str]]:
    session_ids = {row["id"] for row in book["Sessions"] if row["date"] == date}
    return [row for row in book["Sets"] if row["session_id"] in session_ids]


def row_by_date(book: Book, tab: str, date: str) -> dict[str, str]:
    field = DATE_FIELDS.get(tab, "date")
    found = next((row for row in book[tab] if row.get(field) == date), None)
    if found is None:
        raise Missing(tab, date)
    return found


def upsert_by_date(book: Book, tab: str, date: str, fields: dict) -> dict[str, str]:
    if tab not in DATE_TABS:
        raise ValueError(tab)
    merged = {**fields, "date": date}
    found = next((row for row in book[tab] if row["date"] == date), None)
    if found is None:
        return insert_row(book, tab, merged)
    return patch_row(book, tab, found["id"], merged)


def _number(raw: str) -> float:
    if raw == "":
        return -1.0
    return float(raw)


def _lift_name(book: Book, row: dict[str, str]) -> str:
    exercise_id = row.get("exercise_id", "")
    if exercise_id:
        for exercise in book["Exercises"]:
            if exercise["id"] == exercise_id and exercise.get("canonical_name"):
                return exercise["canonical_name"]
    return row.get("name_as_written", "")


def rebuild_daily_view(book: Book) -> None:
    dates: set[str] = set()
    for tab in ("Days", "Sessions", "Nutrition", "Supplements", "ContextNotes", "Media"):
        for row in book[tab]:
            if row.get("date"):
                dates.add(row["date"])
    view: list[dict[str, str]] = []
    for date in sorted(dates):
        day = next((row for row in book["Days"] if row["date"] == date), None)
        sessions = [row for row in book["Sessions"] if row["date"] == date]
        labels: list[str] = []
        for session in sessions:
            if session.get("label") and session["label"] not in labels:
                labels.append(session["label"])
        nutrition = next((row for row in book["Nutrition"] if row["date"] == date), None)
        session_ids = {session["id"] for session in sessions}
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in book["Sets"]:
            if row["session_id"] not in session_ids or row.get("set_type") == "warmup":
                continue
            name = _lift_name(book, row)
            if name:
                grouped.setdefault(name, []).append(row)
        tops: list[str] = []
        for name in sorted(grouped):
            best = max(
                grouped[name],
                key=lambda item: (_number(item.get("weight_lb", "")), _number(item.get("reps", ""))),
            )
            weight = best.get("weight_lb", "")
            reps = best.get("reps", "")
            if weight and reps:
                tops.append(f"{name} {weight}x{reps}")
            elif weight:
                tops.append(f"{name} {weight}")
        context = "; ".join(
            row["text"] for row in book["ContextNotes"] if row["date"] == date and row.get("text")
        )
        supplements = ", ".join(
            row["item"] for row in book["Supplements"] if row["date"] == date and row.get("item")
        )
        view.append({
            "date": date,
            "day_label": ", ".join(labels) if labels else (day["day_label"] if day else ""),
            "bodyweight_lb": day["bodyweight_lb"] if day else "",
            "sleep_hours": day["sleep_hours"] if day else "",
            "steps": day["steps"] if day else "",
            "calories": nutrition["calories"] if nutrition else "",
            "protein_g": nutrition["protein_g"] if nutrition else "",
            "top_lifts": "; ".join(tops),
            "context": context,
            "supplements": supplements,
        })
    book["DailyView"] = view
    book.dirty = True
