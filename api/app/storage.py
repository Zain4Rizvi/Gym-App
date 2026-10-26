import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SPLIT_LABELS = frozenset({"Push", "Pull", "Legs"})
DEFAULT_SPLIT = {
    "Mon": "Push",
    "Tue": "Pull",
    "Wed": "Legs",
    "Thu": "Push",
    "Fri": "Pull",
    "Sat": "Legs",
    "Sun": "",
}


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


def toggle_supplement(book: Book, date: str, item: str) -> dict[str, str] | None:
    folded = item.casefold()
    existing = next(
        (
            row
            for row in book["Supplements"]
            if row["date"] == date and row["item"].casefold() == folded
        ),
        None,
    )
    if existing is not None:
        delete_row(book, "Supplements", existing["id"])
        return None
    checklist = next(
        (row for row in book["SupplementItems"] if row["item"].casefold() == folded),
        None,
    )
    if checklist is None:
        raise Missing("SupplementItems", item)
    return insert_row(
        book,
        "Supplements",
        {
            "date": date,
            "item": checklist["item"],
            "dose": checklist["default_dose"],
            "unit": checklist["unit"],
        },
    )


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


def _ensure_tabs(service, spreadsheet_id: str) -> None:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {sheet["properties"]["title"] for sheet in meta["sheets"]}
    missing = [name for name in TABS if name not in existing]
    if not missing:
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": name}}} for name in missing]},
    ).execute()
    for name in missing:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{name}'!A1",
            valueInputOption="RAW",
            body={"values": [TABS[name]]},
        ).execute()


def load_book(service, spreadsheet_id: str) -> Book:
    _ensure_tabs(service, spreadsheet_id)
    book = empty_book()
    for name, headers in TABS.items():
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"'{name}'!A1:ZZ")
            .execute()
        )
        values = result.get("values", [])
        if not values:
            book.headers[name] = list(headers)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{name}'!A1",
                valueInputOption="RAW",
                body={"values": [list(headers)]},
            ).execute()
            continue
        sheet_headers = list(values[0])
        book.headers[name] = sheet_headers
        width = len(sheet_headers)
        for raw in values[1:]:
            padded = list(raw) + [""] * (width - len(raw))
            by_name = {sheet_headers[index]: padded[index] for index in range(width)}
            row = {header: by_name.get(header, "") for header in headers}
            for header, cell in by_name.items():
                if header not in row:
                    row[header] = cell
            if any(cell != "" for cell in row.values()):
                book[name].append(row)
    return book


def save_book(service, spreadsheet_id: str, book: Book) -> None:
    # ponytail: full-tab rewrite, per-tab dirty ranges if a save gets slow
    data = []
    ranges = []
    for name, headers in TABS.items():
        saved = list(book.headers.get(name) or headers)
        for header in headers:
            if header not in saved:
                saved.append(header)
        values = [saved]
        for row in book[name]:
            values.append([row.get(header, "") for header in saved])
        ranges.append(f"'{name}'!A:ZZ")
        data.append({"range": f"'{name}'!A1", "values": values})
    service.spreadsheets().values().batchClear(
        spreadsheetId=spreadsheet_id,
        body={"ranges": ranges},
    ).execute()
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()


SHARED_BOOK_ID = "shared"
_PASSWORD_ROUNDS = 100_000


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _same(left: str, right: str) -> bool:
    if left == "" or len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)


def _accounts_path() -> Path:
    return data_dir() / "accounts.json"


def _book_path(book_id: str) -> Path:
    if book_id == "" or book_id in {".", ".."} or any(char in book_id for char in "/\\"):
        raise ValueError("book id")
    return data_dir() / "books" / f"{book_id}.json"


def load_accounts() -> list[dict]:
    path = _accounts_path()
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return payload


def save_accounts(accounts: list[dict]) -> None:
    _atomic_write(_accounts_path(), json.dumps(accounts))


def _password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PASSWORD_ROUNDS).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def register_account(email: str, password: str) -> dict[str, str]:
    accounts = load_accounts()
    if any(item["email"].casefold() == email.casefold() for item in accounts):
        raise Duplicate("accounts")
    salt = secrets.token_bytes(16)
    account = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_salt": salt.hex(),
        "password_hash": _password_hash(password, salt),
        "sessions": [],
    }
    token = secrets.token_urlsafe(32)
    account["sessions"].append(_token_hash(token))
    accounts.append(account)
    save_accounts(accounts)
    return {"token": token, "email": email}


def login_account(email: str, password: str) -> dict[str, str] | None:
    accounts = load_accounts()
    account = next((item for item in accounts if item["email"].casefold() == email.casefold()), None)
    if account is None:
        return None
    digest = _password_hash(password, bytes.fromhex(account["password_salt"]))
    if not _same(digest, account["password_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    account["sessions"].append(_token_hash(token))
    save_accounts(accounts)
    return {"token": token, "email": account["email"]}


def _account_in(accounts: list[dict], token: str) -> dict | None:
    if token == "":
        return None
    digest = _token_hash(token)
    for account in accounts:
        for stored in account.get("sessions", []):
            if _same(stored, digest):
                return account
    return None


def account_for_token(token: str) -> dict | None:
    return _account_in(load_accounts(), token)


def _split_label(value) -> str:
    if value in (None, "", "Rest"):
        return ""
    label = str(value)
    if label not in SPLIT_LABELS:
        raise ValueError("split")
    return label


def _stored_label(value) -> str:
    if value in SPLIT_LABELS:
        return str(value)
    return ""


def _public_height(raw):
    if raw in ("", None):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value == int(value):
        return int(value)
    return value


def public_profile(account: dict) -> dict:
    stored = account.get("split")
    if isinstance(stored, dict):
        split = {day: _stored_label(stored.get(day, "")) for day in WEEKDAYS}
    else:
        split = dict(DEFAULT_SPLIT)
    return {
        "email": account["email"],
        "name": str(account.get("name") or ""),
        "height_in": _public_height(account.get("height_in", "")),
        "split": split,
    }


def update_profile(token: str, fields: dict) -> dict | None:
    accounts = load_accounts()
    account = _account_in(accounts, token)
    if account is None:
        return None
    if "height_in" in fields:
        raw = fields["height_in"]
        if raw in (None, ""):
            account["height_in"] = ""
        else:
            try:
                height = float(raw)
            except (TypeError, ValueError):
                raise ValueError("height_in")
            if height < 0:
                raise ValueError("height_in")
            account["height_in"] = int(height) if height == int(height) else height
    if "split" in fields:
        incoming = fields["split"]
        if not isinstance(incoming, dict):
            raise ValueError("split")
        stored = account.get("split")
        if isinstance(stored, dict):
            current = {day: _stored_label(stored.get(day, "")) for day in WEEKDAYS}
        else:
            current = dict(DEFAULT_SPLIT)
        for key, value in incoming.items():
            if key not in WEEKDAYS:
                raise ValueError("split")
            current[key] = _split_label(value)
        account["split"] = current
    save_accounts(accounts)
    return public_profile(account)


def load_local_book(book_id: str) -> Book:
    book = empty_book()
    path = _book_path(book_id)
    if not path.is_file():
        return book
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name in TABS:
        rows = payload.get(name, [])
        if isinstance(rows, list):
            book[name] = rows
    return book


def save_local_book(book_id: str, book: Book) -> None:
    _atomic_write(_book_path(book_id), json.dumps({name: book[name] for name in TABS}))
    book.dirty = False


def sheets_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)
