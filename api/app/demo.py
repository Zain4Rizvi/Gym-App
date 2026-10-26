import hashlib
import uuid
from datetime import date
from pathlib import Path

from api.app.logparse import ALIASES, parse_log
from api.app.schema import TABS
from api.app.storage import (
    DEFAULT_SPLIT,
    Book,
    account_for_token,
    apply_fields,
    load_accounts,
    load_local_book,
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


def _mark(text: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    return f"lifts-txt-1-{digest}-"


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _written(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{_MONTHS[month - 1]} {day}, {year}"


def _document(sessions: list[dict]) -> str:
    return "\n\n".join(f"{_written(session['date'])}\n{session['text']}" for session in sessions)

_CACHE: dict[str, dict[str, list[dict[str, str]]]] = {}


def block(today: date) -> tuple[date, date]:
    return today, today


def lifts_path() -> Path:
    return Path(__file__).resolve().parents[2] / "lifts.txt"


def build_demo_book(today: date | None = None) -> Book:
    text = lifts_path().read_text(encoding="utf-8")
    key = _mark(text)
    cached = _CACHE.get(key)
    if cached is None:
        cached = _snapshot(_book_from_log(text))
        _CACHE[key] = cached
    book = Book()
    for name in TABS:
        book[name] = [dict(row) for row in cached[name]]
    return book


def _imported(book_id: str, mark: str) -> bool:
    if not _book_path(book_id).is_file():
        return False
    book = load_local_book(book_id)
    return any(row.get("client_request_id", "").startswith(mark) for row in book["Notes"])


def ensure_demo(today: date | None = None) -> None:
    account = _ensure_account()
    text = lifts_path().read_text(encoding="utf-8")
    if _imported(account["id"], _mark(text)):
        return
    save_local_book(account["id"], build_demo_book(today or date.today()))


def reset_demo(token: str, today: date | None = None) -> bool:
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


def _book_from_log(text: str) -> Book:
    book = Book()
    mark = _mark(text)
    sessions = parse_log(text)
    if not sessions:
        return book
    note = _row(book, "Notes", {
        "session_date": sessions[-1]["date"],
        "day_label": "",
        "raw_text": _document(sessions),
        "client_request_id": f"{mark}0",
        "parse_status": "done",
    })
    ids: dict[str, str] = {}
    for session in sessions:
        workout = _row(book, "Sessions", {
            "date": session["date"],
            "label": session["label"],
            "note_id": note["id"],
        })
        for exercise in session["exercises"]:
            exercise_id = ids.get(exercise["name"])
            if exercise_id is None:
                exercise_id = _row(book, "Exercises", {
                    "canonical_name": exercise["name"],
                    "status": "active",
                })["id"]
                ids[exercise["name"]] = exercise_id
            for number, item in enumerate(exercise["sets"], start=1):
                fields = {
                    "session_id": workout["id"],
                    "note_id": note["id"],
                    "exercise_id": exercise_id,
                    "name_as_written": exercise["name"],
                    "set_number": str(number),
                    "reps": item["reps"],
                }
                if item["weight"]:
                    fields["weight_lb"] = item["weight"]
                    fields["unit_entered"] = "lb"
                _row(book, "Sets", fields)
    known = {name for _alias, name in ALIASES}
    counts: dict[str, int] = {}
    for row in book["Sets"]:
        counts[row["exercise_id"]] = counts.get(row["exercise_id"], 0) + 1
    drop = {
        row["id"]
        for row in book["Exercises"]
        if row["canonical_name"] not in known and counts.get(row["id"], 0) < 4
    }
    if drop:
        book["Exercises"] = [row for row in book["Exercises"] if row["id"] not in drop]
        book["Sets"] = [row for row in book["Sets"] if row["exercise_id"] not in drop]
    return book
