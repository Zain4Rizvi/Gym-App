import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from api.app.schema import (
    BOOL_FIELDS,
    DAY_LABELS,
    EXERCISE_STATUSES,
    PARSE_STATUSES,
    SET_TYPES,
    SOURCES,
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
_PASSWORD_ROUNDS = 100_000


class Book(dict):
    def __init__(self):
        super().__init__((name, []) for name in TABS)
        self.dirty = False


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
    return False


def insert_row(book: Book, tab: str, fields: dict) -> dict[str, str]:
    if tab not in TABS:
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
    if tab not in TABS:
        raise ValueError(tab)
    row = get_row(book, tab, row_id)
    trial = dict(row)
    apply_fields(tab, trial, fields)
    trial["updated_at"] = utc_now()
    if duplicate(book, tab, trial, ignore_id=row_id):
        raise Duplicate(tab)
    row.clear()
    row.update(trial)
    book.dirty = True
    return row


def delete_row(book: Book, tab: str, row_id: str) -> None:
    if tab not in TABS:
        raise ValueError(tab)
    row = get_row(book, tab, row_id)
    book[tab].remove(row)
    book.dirty = True


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
    if not isinstance(payload, dict):
        return book
    for name in TABS:
        rows = payload.get(name, [])
        if isinstance(rows, list):
            book[name] = rows
    return book


def save_local_book(book_id: str, book: Book) -> None:
    _atomic_write(_book_path(book_id), json.dumps({name: book[name] for name in TABS}))
    book.dirty = False
