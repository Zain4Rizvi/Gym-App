import os
import uuid
from datetime import date, timedelta

from api.app.schema import TABS
from api.app.storage import (
    DEFAULT_SPLIT,
    Book,
    account_for_token,
    apply_fields,
    load_accounts,
    rebuild_daily_view,
    register_account,
    save_accounts,
    save_local_book,
    utc_now,
)
from api.app.storage import _book_path

DEMO_EMAIL = "ava@demo.local"
DEMO_PASSWORD = "demo"
DEMO_NAME = "Ava"
DEMO_HEIGHT = 68

BENCH = ((185, 5), (190, 5), (195, 5), (200, 5), (200, 5), (200, 5), (205, 5), (205, 5))
SQUAT = ((275, 5), (280, 5), (285, 5), (295, 5), (300, 5), (305, 5), (310, 5), (315, 5))
DEAD = ((365, 3), (370, 3), (375, 3), (380, 3), (385, 3), (390, 3), (395, 3), (405, 3))
SLEEP_NOTE = "Slept 5 hours. Bench felt heavy."

_CACHE: dict[str, dict[str, list[dict[str, str]]]] = {}


def block(today: date) -> tuple[date, date]:
    end = today - timedelta(days=1)
    return end - timedelta(days=55), end


def build_demo_book(today: date) -> Book:
    key = today.isoformat()
    cached = _CACHE.get(key)
    if cached is None:
        cached = _snapshot(_generate(today))
        _CACHE[key] = cached
    book = Book()
    for name in TABS:
        book[name] = [dict(row) for row in cached[name]]
    return book


def ensure_demo(today: date | None = None) -> None:
    if os.getenv("SHEET_ID"):
        return
    account = _ensure_account()
    if _book_path(account["id"]).is_file():
        return
    book = build_demo_book(today or date.today())
    save_local_book(account["id"], book)


def reset_demo(token: str, today: date | None = None) -> bool:
    if os.getenv("SHEET_ID"):
        return False
    account = account_for_token(token)
    if account is None or account.get("email", "").casefold() != DEMO_EMAIL:
        return False
    book = build_demo_book(today or date.today())
    save_local_book(account["id"], book)
    return True


def _ensure_account() -> dict:
    accounts = load_accounts()
    found = next((item for item in accounts if item.get("email", "").casefold() == DEMO_EMAIL), None)
    if found is not None:
        return found
    register_account(DEMO_EMAIL, DEMO_PASSWORD)
    accounts = load_accounts()
    account = next(item for item in accounts if item["email"].casefold() == DEMO_EMAIL)
    account["name"] = DEMO_NAME
    account["height_in"] = DEMO_HEIGHT
    account["split"] = dict(DEFAULT_SPLIT)
    save_accounts(accounts)
    return account


def _snapshot(book: Book) -> dict[str, list[dict[str, str]]]:
    return {name: [dict(row) for row in book[name]] for name in TABS}


def _row(book: Book, tab: str, fields: dict) -> dict[str, str]:
    row = {header: "" for header in TABS[tab]}
    now = utc_now()
    row["id"] = str(uuid.uuid4())
    row["created_at"] = now
    row["updated_at"] = now
    row["source"] = "import"
    apply_fields(tab, row, fields)
    if tab == "Notes":
        row["parse_status"] = "done"
    book[tab].append(row)
    return row


def _sets(book: Book, session_id: str, note_id: str, exercise_id: str, name: str, weight: int, reps: int) -> None:
    start = 1
    if weight:
        warm = int(round(weight * 0.5 / 5) * 5)
        _row(book, "Sets", {
            "session_id": session_id,
            "note_id": note_id,
            "exercise_id": exercise_id,
            "name_as_written": name,
            "set_number": "1",
            "weight_lb": warm,
            "unit_entered": "lb",
            "reps": 5,
            "set_type": "warmup",
        })
        start = 2
    for offset in range(3):
        fields: dict = {
            "session_id": session_id,
            "note_id": note_id,
            "exercise_id": exercise_id,
            "name_as_written": name,
            "set_number": str(start + offset),
            "reps": reps,
        }
        if weight:
            fields["weight_lb"] = weight
            fields["unit_entered"] = "lb"
        _row(book, "Sets", fields)


def _generate(today: date) -> Book:
    start, end = block(today)
    book = Book()
    catalog = {
        "Bench Press": ("horizontal push", "barbell", "chest", "shoulders, triceps"),
        "Overhead Press": ("vertical push", "barbell", "shoulders", "triceps"),
        "Incline Dumbbell Press": ("horizontal push", "dumbbell", "chest", "shoulders"),
        "Deadlift": ("hinge", "barbell", "back", "hamstrings"),
        "Barbell Row": ("horizontal pull", "barbell", "back", "biceps"),
        "Pull-up": ("vertical pull", "bodyweight", "back", "biceps"),
        "Back Squat": ("squat", "barbell", "quads", "glutes"),
        "Romanian Deadlift": ("hinge", "barbell", "hamstrings", "glutes"),
        "Leg Press": ("squat", "machine", "quads", "glutes"),
    }
    ids = {}
    for name, (pattern, equipment, primary, secondary) in catalog.items():
        ids[name] = _row(book, "Exercises", {
            "canonical_name": name,
            "movement_pattern": pattern,
            "equipment": equipment,
            "primary_muscles": primary,
            "secondary_muscles": secondary,
            "status": "active",
        })["id"]
    _row(book, "SupplementItems", {"item": "Creatine", "default_dose": "5", "unit": "g", "active": True})

    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    span = max((end - start).days, 1)
    for index, current in enumerate(days):
        week = index // 7
        iso = current.isoformat()
        travel = week == 4
        weight = 186.4 + (181.2 - 186.4) * (index / span)
        if 0 < index < span:
            weight += ((index % 5) - 2) * 0.1
        _row(book, "Days", {
            "date": iso,
            "bodyweight_lb": round(weight, 1),
            "sleep_hours": 5 if travel else 7.5,
            "steps": 3500 if travel else 9000,
        })
        _row(book, "Nutrition", {
            "date": iso,
            "calories": 1900 if travel else 2460 + (index % 5) * 20,
            "protein_g": 140 if travel else 176 + (index % 3) * 4,
            "carbs_g": 180 if travel else 250,
            "fat_g": 60 if travel else 70,
        })
        if not travel:
            _row(book, "Supplements", {"date": iso, "item": "Creatine", "dose": "5", "unit": "g"})

    for week in range(8):
        program = {
            "Push": [
                ("Bench Press", BENCH[week][0], BENCH[week][1]),
                ("Overhead Press", 95 + week * 5, 5),
                ("Incline Dumbbell Press", 50 + (week // 2) * 5, 8),
            ],
            "Pull": [
                ("Deadlift", DEAD[week][0], DEAD[week][1]),
                ("Barbell Row", 135 + week * 5, 8),
                ("Pull-up", 0, 6 + week // 2),
            ],
            "Legs": [
                ("Back Squat", SQUAT[week][0], SQUAT[week][1]),
                ("Romanian Deadlift", 185 + week * 10, 6),
                ("Leg Press", 180 + week * 10, 8),
            ],
        }
        for offset, label in ((0, "Push"), (2, "Pull"), (4, "Legs")):
            current = start + timedelta(days=week * 7 + offset)
            iso = current.isoformat()
            lines = [label]
            for name, weight, reps in program[label]:
                line = f"{name} {weight}x{reps}" if weight else f"{name} x{reps}"
                lines.extend((line, line, line))
            note = _row(book, "Notes", {
                "session_date": iso,
                "day_label": label,
                "raw_text": "\n".join(lines),
                "client_request_id": f"seed-{iso}-{label}",
                "parse_status": "done",
            })
            session = _row(book, "Sessions", {
                "date": iso,
                "label": label,
                "note_id": note["id"],
            })
            for name, weight, reps in program[label]:
                _sets(book, session["id"], note["id"], ids[name], name, weight, reps)
            day = next(row for row in book["Days"] if row["date"] == iso)
            day["day_label"] = label
            if week == 4 and label == "Push":
                _row(book, "ContextNotes", {
                    "date": iso,
                    "text": SLEEP_NOTE,
                    "tags": "sleep,travel",
                })

    rebuild_daily_view(book)
    return book
