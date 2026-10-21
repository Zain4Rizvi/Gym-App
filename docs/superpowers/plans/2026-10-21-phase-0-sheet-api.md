# Phase 0 Sheet API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI service that reads and writes every Gym Dashboard sheet tab through one storage module, protected by a shared bearer token, and deployable to Cloud Run.

**Architecture:** Rows live in a `Book` dict keyed by tab name. `api/app/storage.py` is the only module that talks to Google Sheets (`load_book` / `save_book`). Everything else calls functions such as `insert_row` and `upsert_by_date`. Tests pass a `Book` and never open a network socket. The default pytest run skips the live sheet test.

**Tech Stack:** Python 3.14, uv, FastAPI, uvicorn, pytest, httpx, google-api-python-client, Cloud Run.

Spec: `docs/superpowers/specs/2026-10-21-gym-dashboard-design.md`

The repo today is a uv scaffold: `main.py` prints hello, `pyproject.toml` has no dependencies, `.python-version` is `3.14`. Run every command from the repo root.

Phases 1–5 are separate plans. This plan does not add a Gemini client, a photo client, or an Expo app.

## Global Constraints

- One person, one Google Sheet. No storage ABC and no second store class.
- `Authorization: Bearer <AUTH_TOKEN>` on every route except `GET /health`. Compare with `secrets.compare_digest`. A mismatch is 401.
- Dates are `YYYY-MM-DD` from the client. Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ`. Ids are uuid4 strings.
- An empty cell is not recorded. `0` is a real zero. Booleans are the strings `TRUE` and `FALSE`.
- `source` is `gemini`, `user`, or `import`. Inserts default to `user`.
- Partial write: a field absent from the request stays, JSON `null` clears it.
- Kg converts only when that write includes `weight_lb` and the unit is `kg`: `round(weight * 2.2046226218, 2)`, stored as `weight_lb` with two decimal places. A later patch that does not send `weight_lb` must not convert again.
- `POST /notes` requires `client_request_id` (400 if missing), forces `parse_status=pending`, and does not call Gemini. The same id returns the existing note and does not change it.
- `POST /notes/{id}/parse` returns 503 and does not change the note.
- DailyView is rebuilt in code after a mutation. It is not a formula tab.
- Sheets IO uses header names. An unknown column survives load → save. Column order does not matter.
- The live sheet test runs only when both `SHEET_ID` and `GOOGLE_APPLICATION_CREDENTIALS` are set, and it skips if `1900-01-01` is already a Days row.
- The container image is `python:3.14-slim`. Cloud Run allows unauthenticated invocations at the edge. The bearer token is the lock.

## File structure

| Path | Responsibility |
|---|---|
| `api/app/schema.py` | Tab names, header order, enums, URL slugs |
| `api/app/storage.py` | Book, row functions, DailyView, the only Sheets IO |
| `api/app/auth.py` | Bearer check |
| `api/app/main.py` | Routes |
| `api/tests/test_schema.py` | Header lock |
| `api/tests/test_storage.py` | Row rules and DailyView |
| `api/tests/test_sheets.py` | Fake Sheets round trip and skipped live test |
| `api/tests/test_api.py` | HTTP |
| `Dockerfile` | Cloud Run image |
| `README.md` | Test and deploy commands |

Delete the scaffold `main.py` in Task 1. Nothing imports it.

---

### Task 1: Schema and cell encoding

**Files:**
- Create: `api/__init__.py`
- Create: `api/app/__init__.py`
- Create: `api/app/schema.py`
- Create: `api/app/storage.py`
- Create: `api/tests/test_schema.py`
- Modify: `pyproject.toml`
- Delete: `main.py`

**Interfaces:**
- Consumes: nothing
- Produces: `TABS`, `ROW_TABS`, `DATE_TABS`, `PATHS`, `DATE_FIELDS`, enum frozensets, `Book`, `empty_book()`, `encode(field, value) -> str`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_schema.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest api/tests/test_schema.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api'`

- [ ] **Step 3: Add dependencies and the schema**

Run:

```powershell
uv add fastapi uvicorn
uv add --dev pytest httpx
```

Append this to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["api/tests"]
```

Delete `main.py`.

Create empty `api/__init__.py` and `api/app/__init__.py`.

Create `api/app/schema.py`:

```python
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
```

Create `api/app/storage.py`:

```python
from api.app.schema import BOOL_FIELDS, TABS


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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest api/tests/test_schema.py -v`

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock api/__init__.py api/app/__init__.py api/app/schema.py api/app/storage.py api/tests/test_schema.py
git add -u main.py
git commit -m "feat: lock sheet columns and cell encoding"
```

---

### Task 2: Row storage

**Files:**
- Modify: `api/app/storage.py`
- Create: `api/tests/test_storage.py`

**Interfaces:**
- Consumes: `Book`, `encode`, `TABS`, `ROW_TABS`, enums
- Produces: `Duplicate`, `Missing`, `insert_row(book, tab, fields)`, `get_row(book, tab, row_id)`, `patch_row(book, tab, row_id, fields)`, `delete_row(book, tab, row_id)`, `rows_by_field(book, tab, field, value)`, `sets_on_date(book, date)`, `row_by_date(book, tab, date)`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_storage.py`:

```python
import pytest

from api.app.storage import Book, Duplicate, Missing, delete_row, empty_book, get_row, insert_row, patch_row


def test_insert_patch_null_and_ignore_unknown_field():
    book = empty_book()
    row = insert_row(book, "Exercises", {"canonical_name": "Bench Press", "status": "active", "nope": "x"})
    assert row["id"]
    assert row["source"] == "user"
    assert row["created_at"].endswith("Z")
    assert "nope" not in row
    assert row["needs_review"] == ""
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest api/tests/test_storage.py -v`

Expected: FAIL with `ImportError` on `insert_row`.

- [ ] **Step 3: Implement row functions**

Append to `api/app/storage.py`:

```python
import uuid
from datetime import datetime, timezone

from api.app.schema import (
    DATE_FIELDS,
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


def apply_fields(tab: str, row: dict[str, str], fields: dict) -> None:
    validate_fields(tab, fields)
    allowed = set(TABS[tab]) - {"id", "created_at"}
    for key, value in fields.items():
        if key not in allowed:
            continue
        row[key] = "" if value is None else encode(key, value)


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
    book.dirty = True
    return row


def delete_row(book: Book, tab: str, row_id: str) -> None:
    if tab not in ROW_TABS:
        raise ValueError(tab)
    row = get_row(book, tab, row_id)
    book[tab].remove(row)
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
```

Paste the functions after `encode`. Merge this import block into the top of `api/app/storage.py` so each name is imported once:

```python
import uuid
from datetime import datetime, timezone

from api.app.schema import (
    BOOL_FIELDS,
    DATE_FIELDS,
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest api/tests/test_schema.py api/tests/test_storage.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add api/app/storage.py api/tests/test_storage.py
git commit -m "feat: store editable rows with unique keys"
```

---

### Task 3: Date upsert and kilogram entry

**Files:**
- Modify: `api/app/storage.py`
- Modify: `api/tests/test_storage.py`

**Interfaces:**
- Consumes: `insert_row`, `patch_row`, `apply_fields`
- Produces: `upsert_by_date(book, tab, date, fields)`, `canonicalize_weight(row, fields)` called from `apply_fields` for Sets

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest api/tests/test_storage.py::test_date_upsert_is_partial_and_kg_converts_once -v`

Expected: FAIL with `ImportError` on `upsert_by_date`

- [ ] **Step 3: Implement upsert and one-time kg conversion**

Add `LB_PER_KG = 2.2046226218` near the top of `api/app/storage.py`.

Add `canonicalize_weight` and call it at the end of `apply_fields`. Replace `apply_fields` with:

```python
LB_PER_KG = 2.2046226218


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
```

Append:

```python
def upsert_by_date(book: Book, tab: str, date: str, fields: dict) -> dict[str, str]:
    if tab not in DATE_TABS:
        raise ValueError(tab)
    merged = {**fields, "date": date}
    found = next((row for row in book[tab] if row["date"] == date), None)
    if found is None:
        return insert_row(book, tab, merged)
    return patch_row(book, tab, found["id"], merged)
```

Import `DATE_TABS` from `api.app.schema` in the existing import block.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest api/tests/test_storage.py api/tests/test_schema.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add api/app/storage.py api/tests/test_storage.py
git commit -m "feat: upsert a date and convert kilograms on entry"
```

---

### Task 4: Daily view

**Files:**
- Modify: `api/app/storage.py`
- Modify: `api/tests/test_storage.py`

**Interfaces:**
- Consumes: `Book` tabs Days, Sessions, Sets, Exercises, Nutrition, Supplements, ContextNotes, Media
- Produces: `rebuild_daily_view(book)` which replaces `book["DailyView"]`. `insert_row`, `patch_row`, and `delete_row` call it after a real mutation. The idempotent note return does not.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest api/tests/test_storage.py::test_daily_view_joins_the_day_and_picks_the_top_set -v`

Expected: FAIL because `book["DailyView"]` is empty (`IndexError` or an assertion on `len(view)`).

- [ ] **Step 3: Rebuild the view after mutations**

Append to `api/app/storage.py`:

```python
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
```

In `insert_row`, `patch_row`, and `delete_row`, call `rebuild_daily_view(book)` after the book changes and before `return`. Do not call it on the idempotent Notes early return.

`insert_row` tail:

```python
    book[tab].append(row)
    rebuild_daily_view(book)
    book.dirty = True
    return row
```

`patch_row` tail:

```python
    row.clear()
    row.update(trial)
    rebuild_daily_view(book)
    book.dirty = True
    return row
```

`delete_row` tail:

```python
    book[tab].remove(row)
    rebuild_daily_view(book)
    book.dirty = True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest api/tests/test_storage.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add api/app/storage.py api/tests/test_storage.py
git commit -m "feat: rebuild the daily view from logged rows"
```

---

### Task 5: Sheets load and save

**Files:**
- Modify: `api/app/storage.py`
- Create: `api/tests/test_sheets.py`

**Interfaces:**
- Consumes: `Book`, `TABS`, `insert_row`
- Produces: `load_book(service, spreadsheet_id) -> Book`, `save_book(service, spreadsheet_id, book)`, `sheets_service()`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_sheets.py`:

```python
import os

import pytest

from api.app.schema import TABS
from api.app.storage import insert_row, load_book, save_book


def _title(cell_range: str) -> str:
    return cell_range.split("!")[0].strip("'")


def _write_leaving_tail(tabs: dict, title: str, values: list) -> None:
    old = tabs.get(title, [])
    if len(old) > len(values):
        tabs[title] = values + old[len(values) :]
    else:
        tabs[title] = values


class _Call:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class FakeValues:
    def __init__(self, tabs: dict):
        self.tabs = tabs

    def get(self, spreadsheetId: str, range: str):
        title = _title(range)
        return _Call(lambda: {"values": [list(row) for row in self.tabs.get(title, [])]})

    def update(self, spreadsheetId: str, range: str, valueInputOption: str, body: dict):
        title = _title(range)

        def run():
            _write_leaving_tail(self.tabs, title, body["values"])
            return {}

        return _Call(run)

    def batchClear(self, spreadsheetId: str, body: dict):
        def run():
            for cell_range in body["ranges"]:
                self.tabs[_title(cell_range)] = []
            return {}

        return _Call(run)

    def batchUpdate(self, spreadsheetId: str, body: dict):
        def run():
            for item in body["data"]:
                _write_leaving_tail(self.tabs, _title(item["range"]), item["values"])
            return {}

        return _Call(run)


class FakeSheets:
    def __init__(self, tabs: dict):
        self.tabs = tabs

    def get(self, spreadsheetId: str):
        return _Call(lambda: {"sheets": [{"properties": {"title": name}} for name in self.tabs]})

    def batchUpdate(self, spreadsheetId: str, body: dict):
        def run():
            for request in body["requests"]:
                self.tabs[request["addSheet"]["properties"]["title"]] = []
            return {}

        return _Call(run)

    def values(self):
        return FakeValues(self.tabs)


class FakeService:
    def __init__(self):
        self.tabs = {"Sheet1": [["keep"]]}

    def spreadsheets(self):
        return FakeSheets(self.tabs)


def test_roundtrip_keeps_extra_columns_and_drops_deleted_rows():
    service = FakeService()
    service.tabs["Days"] = [[
        "bodyweight_lb", "date", "fiber_g", "id", "created_at", "updated_at",
        "source", "sleep_hours", "steps", "day_label", "summary",
    ], [
        "180", "2026-09-22", "12", "abc", "t", "t", "user", "8", "1000", "Push", "",
    ], [
        "181", "2026-09-23", "0", "def", "t", "t", "user", "", "", "", "",
    ]]
    book = load_book(service, "sheet")
    assert book["Days"][0]["fiber_g"] == "12"
    assert book["Days"][0]["date"] == "2026-09-22"
    assert service.tabs["Sheet1"] == [["keep"]]
    book["Days"][0]["bodyweight_lb"] = "179"
    book["Days"] = book["Days"][:1]
    save_book(service, "sheet", book)
    loaded = load_book(service, "sheet")
    assert len(loaded["Days"]) == 1
    assert loaded["Days"][0]["fiber_g"] == "12"
    assert loaded["Days"][0]["bodyweight_lb"] == "179"
    assert loaded["Days"][0]["id"] == "abc"


def test_save_writes_schema_headers_for_a_new_workbook():
    service = FakeService()
    book = load_book(service, "sheet")
    insert_row(book, "Days", {"date": "2026-09-22", "bodyweight_lb": 180})
    save_book(service, "sheet", book)
    assert service.tabs["Days"][0] == TABS["Days"]
    loaded = load_book(service, "sheet")
    assert loaded["Days"][0]["date"] == "2026-09-22"
    assert loaded["Days"][0]["bodyweight_lb"] == "180"


@pytest.mark.skipif(
    not os.getenv("SHEET_ID") or not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="live sheet credentials are not set",
)
def test_live_sheet_roundtrip():
    from api.app.storage import sheets_service

    service = sheets_service()
    book = load_book(service, os.environ["SHEET_ID"])
    if any(row["date"] == "1900-01-01" for row in book["Days"]):
        pytest.skip("probe date is already in the sheet")
    try:
        insert_row(book, "Days", {"date": "1900-01-01", "bodyweight_lb": 1})
        save_book(service, os.environ["SHEET_ID"], book)
        loaded = load_book(service, os.environ["SHEET_ID"])
        probe = next(row for row in loaded["Days"] if row["date"] == "1900-01-01")
        assert probe["bodyweight_lb"] == "1"
    finally:
        from api.app.storage import rebuild_daily_view

        current = load_book(service, os.environ["SHEET_ID"])
        current["Days"] = [row for row in current["Days"] if row["date"] != "1900-01-01"]
        rebuild_daily_view(current)
        save_book(service, os.environ["SHEET_ID"], current)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv add google-api-python-client google-auth`

Then: `uv run pytest api/tests/test_sheets.py -v`

Expected: FAIL with `ImportError` on `load_book`. The live test is skipped unless both env vars are set.

- [ ] **Step 3: Implement load and save**

Append to `api/app/storage.py`:

```python
import os


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


def sheets_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)
```

`import os` belongs with the other imports at the top of the file.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest api/tests/test_sheets.py api/tests/test_storage.py -v`

Expected: PASS. `test_live_sheet_roundtrip` is SKIPPED when the env vars are unset.

- [ ] **Step 5: Commit**

```powershell
git add api/app/storage.py api/tests/test_sheets.py pyproject.toml uv.lock
git commit -m "feat: read and write the workbook by header name"
```

---

### Task 6: HTTP API

**Files:**
- Create: `api/app/auth.py`
- Create: `api/app/main.py`
- Create: `api/tests/test_api.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: every storage function from Tasks 2–5, `PATHS`, `DATE_TABS`, `DATE_FIELDS`
- Produces: FastAPI `app`, `get_book`, `require_token`. Routes listed in the spec, plus `GET /daily-view` and `GET /daily-view/{date}` so the rebuilt tab is readable. Days and Nutrition use `PUT /{path}/{YYYY-MM-DD}`. `GET /days/{key}` treats a date as a date and any other key as an id. `POST` exists for every row tab except Days and Nutrition. `POST /notes` returns `{"note", "sets"}`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_api.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.main import app, get_book
from api.app.storage import empty_book

HEADER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SHEET_ID", raising=False)
    book = empty_book()

    def override():
        yield book

    app.dependency_overrides[get_book] = override
    with TestClient(app) as client:
        yield client, book
    app.dependency_overrides.clear()


def test_health_is_open_and_writes_require_the_token(api):
    client, _book = api
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"ok": True}
    assert client.post("/notes", json={"client_request_id": "a", "raw_text": "x"}).status_code == 401
    assert client.post(
        "/notes",
        json={"client_request_id": "a", "raw_text": "x"},
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401


def test_notes_stay_pending_and_parse_does_not_touch_them(api):
    client, book = api
    missing = client.post("/notes", json={"raw_text": "bench"}, headers=HEADER)
    assert missing.status_code == 400
    first = client.post(
        "/notes",
        json={"client_request_id": "req-1", "raw_text": "bench", "session_date": "2026-09-22", "day_label": "Push"},
        headers=HEADER,
    )
    assert first.status_code == 200
    body = first.json()
    assert body["note"]["parse_status"] == "pending"
    assert body["sets"] == []
    second = client.post("/notes", json={"client_request_id": "req-1", "raw_text": "other"}, headers=HEADER)
    assert second.json()["note"]["id"] == body["note"]["id"]
    assert second.json()["note"]["raw_text"] == "bench"
    parsed = client.post(f"/notes/{body['note']['id']}/parse", headers=HEADER)
    assert parsed.status_code == 503
    assert book["Notes"][0]["parse_status"] == "pending"
    assert book["Sessions"] == []
    assert book["Sets"] == []


def test_day_put_is_partial_and_builds_the_daily_view(api):
    client, _book = api
    created = client.put("/days/2026-09-22", json={"bodyweight_lb": 180, "day_label": "Push"}, headers=HEADER)
    assert created.status_code == 200
    updated = client.put("/days/2026-09-22", json={"sleep_hours": None}, headers=HEADER)
    assert updated.json()["bodyweight_lb"] == "180"
    assert updated.json()["sleep_hours"] == ""
    zero = client.put("/days/2026-09-23", json={"bodyweight_lb": 0}, headers=HEADER)
    assert zero.json()["bodyweight_lb"] == "0"
    view = client.get("/daily-view/2026-09-22", headers=HEADER)
    assert view.status_code == 200
    assert view.json()["bodyweight_lb"] == "180"
    assert client.get("/days/1900-01-01", headers=HEADER).status_code == 404


def test_sets_by_date_kg_and_supplement_conflict(api):
    client, book = api
    session = client.post("/sessions", json={"date": "2026-09-22", "label": "Push"}, headers=HEADER)
    assert session.status_code == 200
    lifted = client.post(
        "/sets",
        json={"session_id": session.json()["id"], "weight_lb": 20, "unit_entered": "kg", "set_number": "1"},
        headers=HEADER,
    )
    assert lifted.status_code == 200
    assert lifted.json()["weight_lb"] == "44.09"
    listed = client.get("/sets", params={"date": "2026-09-22"}, headers=HEADER)
    assert len(listed.json()) == 1
    assert client.post("/sets", json={"set_type": "cardio"}, headers=HEADER).status_code == 400
    assert client.post(
        "/supplements",
        json={"date": "2026-09-22", "item": "Creatine", "dose": "5"},
        headers=HEADER,
    ).status_code == 200
    assert client.post(
        "/supplements",
        json={"date": "2026-09-22", "item": "creatine", "dose": "5"},
        headers=HEADER,
    ).status_code == 409
    removed = client.delete(f"/sets/{lifted.json()['id']}", headers=HEADER)
    assert removed.status_code == 204
    assert book["Sets"] == []


def test_every_catalog_tab_roundtrips(api):
    client, _book = api
    created = client.post(
        "/exercises",
        json={"canonical_name": "Squat", "status": "active", "primary_muscles": "quads"},
        headers=HEADER,
    )
    assert created.status_code == 200
    row_id = created.json()["id"]
    assert client.get(f"/exercises/{row_id}", headers=HEADER).json()["canonical_name"] == "Squat"
    patched = client.patch(f"/exercises/{row_id}", json={"equipment": "rack"}, headers=HEADER)
    assert patched.json()["equipment"] == "rack"
    assert client.post(
        "/aliases",
        json={"alias": "Incline Dumbell", "exercise_id": row_id, "day_label": "Push"},
        headers=HEADER,
    ).status_code == 200
    assert client.post(
        "/supplement-items",
        json={"item": "Creatine", "default_dose": "5", "unit": "g", "active": True},
        headers=HEADER,
    ).json()["active"] == "TRUE"
    assert client.post(
        "/context-notes",
        json={"date": "2026-09-22", "text": "travel day", "tags": "travel"},
        headers=HEADER,
    ).status_code == 200
    assert client.post(
        "/media",
        json={"date": "2026-09-22", "pose": "front", "storage_uri": "gs://bucket/a.jpg"},
        headers=HEADER,
    ).status_code == 200
    assert client.get("/exercises", headers=HEADER).status_code == 200


def test_app_source_does_not_import_gemini():
    for path in Path("api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "generativeai" not in text
        assert "google.genai" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest api/tests/test_api.py -v`

Expected: FAIL with `ModuleNotFoundError` for `api.app.main` or `api.app.auth`.

- [ ] **Step 3: Implement auth and routes**

Append `.env` to `.gitignore` if it is not already there.

Create `api/app/auth.py`:

```python
import os
import secrets

from fastapi import Header, HTTPException


def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("AUTH_TOKEN", "")
    scheme, _, got = (authorization or "").partition(" ")
    if scheme != "Bearer" or expected == "" or not secrets.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="unauthorized")
```

Create `api/app/main.py`:

```python
import os
import re

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse

from api.app.auth import require_token
from api.app.schema import DATE_FIELDS, DATE_TABS, PATHS
from api.app.storage import (
    Book,
    Duplicate,
    Missing,
    delete_row,
    get_row,
    insert_row,
    load_book,
    patch_row,
    rebuild_daily_view,
    row_by_date,
    rows_by_field,
    save_book,
    sets_on_date,
    sheets_service,
    upsert_by_date,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI()


def get_book():
    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        raise HTTPException(status_code=500, detail="SHEET_ID is not set")
    service = sheets_service()
    book = load_book(service, sheet_id)
    try:
        yield book
    finally:
        if book.dirty:
            save_book(service, sheet_id, book)


@app.exception_handler(Missing)
def missing_handler(_request, exc: Missing):
    return JSONResponse(status_code=404, content={"detail": exc.row_id})


@app.exception_handler(Duplicate)
def duplicate_handler(_request, exc: Duplicate):
    return JSONResponse(status_code=409, content={"detail": exc.tab})


@app.exception_handler(ValueError)
def value_handler(_request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"ok": True}


def mount(router: APIRouter) -> None:
    @router.post("/notes")
    def create_note(body: dict = Body(...), book: Book = Depends(get_book)):
        if not str(body.get("client_request_id") or ""):
            raise HTTPException(status_code=400, detail="client_request_id is required")
        note = insert_row(book, "Notes", body)
        sets = [row for row in book["Sets"] if row["note_id"] == note["id"]]
        return {"note": note, "sets": sets}

    @router.post("/notes/{row_id}/parse")
    def parse_note(row_id: str, book: Book = Depends(get_book)):
        get_row(book, "Notes", row_id)
        raise HTTPException(status_code=503, detail="parser not configured")

    @router.post("/daily-view/rebuild")
    def rebuild(book: Book = Depends(get_book)):
        rebuild_daily_view(book)
        return book["DailyView"]

    @router.get("/daily-view")
    def daily_all(book: Book = Depends(get_book)):
        return book["DailyView"]

    @router.get("/daily-view/{date}")
    def daily_one(date: str, book: Book = Depends(get_book)):
        return row_by_date(book, "DailyView", date)

    for tab, path in PATHS.items():
        add_item_routes(router, tab, path)
        if tab in DATE_TABS:
            add_put_by_date(router, tab, path)
        elif tab != "Notes":
            add_post(router, tab, path)
        add_list(router, tab, path)


def add_item_routes(router: APIRouter, tab: str, path: str) -> None:
    @router.get(f"/{path}/{{key}}", operation_id=f"get_{path}")
    def read(key: str, book: Book = Depends(get_book), tab: str = tab):
        if tab in DATE_TABS and DATE_RE.fullmatch(key):
            return row_by_date(book, tab, key)
        return get_row(book, tab, key)

    @router.patch(f"/{path}/{{row_id}}", operation_id=f"patch_{path}")
    def patch(row_id: str, body: dict = Body(...), book: Book = Depends(get_book), tab: str = tab):
        return patch_row(book, tab, row_id, body)

    @router.delete(f"/{path}/{{row_id}}", operation_id=f"delete_{path}")
    def remove(row_id: str, book: Book = Depends(get_book), tab: str = tab):
        delete_row(book, tab, row_id)
        return Response(status_code=204)


def add_put_by_date(router: APIRouter, tab: str, path: str) -> None:
    @router.put(f"/{path}/{{date}}", operation_id=f"put_{path}")
    def put(date: str, body: dict = Body(...), book: Book = Depends(get_book), tab: str = tab):
        if DATE_RE.fullmatch(date) is None:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        return upsert_by_date(book, tab, date, body)


def add_post(router: APIRouter, tab: str, path: str) -> None:
    @router.post(f"/{path}", operation_id=f"post_{path}")
    def create(body: dict = Body(...), book: Book = Depends(get_book), tab: str = tab):
        return insert_row(book, tab, body)


def add_list(router: APIRouter, tab: str, path: str) -> None:
    @router.get(f"/{path}", operation_id=f"list_{path}")
    def listing(date: str | None = None, book: Book = Depends(get_book), tab: str = tab):
        if tab == "Sets" and date is not None:
            return sets_on_date(book, date)
        field = DATE_FIELDS.get(tab)
        if date is not None and field:
            return rows_by_field(book, tab, field, date)
        return list(book[tab])


router = APIRouter(dependencies=[Depends(require_token)])
mount(router)
app.include_router(router)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -v`

Expected: PASS. The live sheet test is SKIPPED when credentials are unset.

- [ ] **Step 5: Commit**

```powershell
git add api/app/auth.py api/app/main.py api/tests/test_api.py .gitignore
git commit -m "feat: serve every tab behind the shared token"
```

---

### Task 7: Cloud Run image

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: `api.app.main:app`, `uv.lock`
- Produces: an image that listens on port 8080. No deploy is run from the test suite.

- [ ] **Step 1: Write the image files**

Create `Dockerfile`:

```dockerfile
FROM python:3.14-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

COPY api ./api

EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Create `.dockerignore`:

```
.venv
.git
**/__pycache__
.pytest_cache
```

Replace `README.md` with:

````markdown
# Gym App

Phase 0 is the sheet API. Tests use an in-memory workbook.

```powershell
uv run pytest
```

The API process needs `AUTH_TOKEN`, `SHEET_ID`, and `GOOGLE_APPLICATION_CREDENTIALS` pointing at a service-account JSON file. Share the Google Sheet with that account's `client_email` as Editor.

Cloud Run is publicly invocable. The bearer token is the application lock.

```powershell
gcloud secrets create gym-sheets-sa --data-file=PATH_TO_SA.json
$projectNumber = gcloud projects describe (gcloud config get-value project) --format="value(projectNumber)"
gcloud secrets add-iam-policy-binding gym-sheets-sa --member="serviceAccount:${projectNumber}-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
gcloud run deploy gym-api --source . --region us-east1 --allow-unauthenticated --timeout=60 --set-env-vars "SHEET_ID=YOUR_SHEET_ID,AUTH_TOKEN=YOUR_TOKEN,GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json" --set-secrets "/secrets/sa.json=gym-sheets-sa:latest"
```

`GET /health` needs no token. Every other route sends `Authorization: Bearer YOUR_TOKEN`.
````

- [ ] **Step 2: Run the test suite**

Run: `uv run pytest -v`

Expected: PASS, with `test_live_sheet_roundtrip` skipped when credentials are unset.

- [ ] **Step 3: Build the image**

Run: `docker build -t gym-api .`

Expected: exit 0. If Docker is not installed, stop and report that. Do not skip the pytest run.

- [ ] **Step 4: Commit**

```powershell
git add Dockerfile .dockerignore README.md
git commit -m "feat: package the API for Cloud Run"
```

Deploy only when a sheet, a service account, and `gcloud` auth already exist. Use the README commands. Do not invent a project id or a token.

---

## Spec coverage

- Phase 0 done line: Tasks 2–6 cover read/write of every tab and DailyView. Task 6 covers the token. Task 7 covers the image. Deploy stays a manual README command because it needs the user's Google project.
- `POST /notes` pending, idempotent `client_request_id`, parse 503: Task 6.
- Kg conversion, partial null, unique keys, `0` vs empty, booleans: Tasks 1–3.
- Header-name IO and extra columns: Task 5.
- No Gemini import: Task 6 source test.
- Phases 1–5, meals, muscle table, edit history, offline queue: not in this plan.

## Self-review notes

- `POST /notes/{id}/parse` is 503 even if `GEMINI_API_KEY` is set. Phase 0 has no parser. Phase 1 replaces `parse_note`.
- `GET /daily-view` is extra to the spec's route list so the rebuilt tab can be read through the API.
- Days `GET /days/2026-09-22` is a date lookup. `PATCH /days/{uuid}` is the id update. `PUT` is the date upsert.
