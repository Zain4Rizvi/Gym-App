# Phase 2 Daily Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log one full day through the existing sheet routes: a Days upsert, a Nutrition upsert, supplement checklist taps, and a context note.

**Architecture:** Days, Nutrition, SupplementItems, Supplements, and ContextNotes already go through `insert_row`, `upsert_by_date`, and `delete_row`. Phase 2 does not add a second log API. The one missing behavior is the checklist tap: `POST /supplements` with an explicit dose still inserts, and a duplicate `(date, item)` is still 409. A tap is `POST /supplements/toggle` with `date` and `item`. No row today inserts a Supplements row from that checklist item's `default_dose` and `unit`. A row today deletes it. Tests use the in-memory `Book`.

**Tech Stack:** Python 3.14, uv, FastAPI, pytest, httpx. No new dependency.

Spec: `docs/superpowers/specs/2026-10-21-gym-dashboard-design.md`

I'm using the writing-plans skill to create this plan. This session implements the plan inline and does not commit.

## Global Constraints

- Dates are `YYYY-MM-DD` from the client. Timestamps are UTC. Ids are uuid4 strings.
- An empty cell is not recorded. `0` is a real zero. Booleans are the strings `TRUE` and `FALSE`.
- Nutrition is one row per date: `calories`, `protein_g`, `carbs_g`, `fat_g`. No Meals table. No micro columns.
- Days and Nutrition upsert by `date`. A field absent from the request stays. JSON `null` clears it.
- `weight_lb` converts from kg only when that write includes `weight_lb` and `unit_entered` is `kg`: `round(weight * 2.2046226218, 2)`. Days stores `bodyweight_lb` and has no `unit_entered`. Do not convert bodyweight.
- SupplementItems is the checklist. Supplements is one item per date. Unique supplement key is `(date, item)` case-insensitive. Unique checklist key is `item`, case-insensitive.
- Context tags are optional and comma-separated from `sleep`, `illness`, `stress`, `travel`. This phase does not call Gemini to suggest them.
- The tab comes from the path. Close over the sheet name. Do not add a route parameter named `tab`.
- `storage.py` stays the only Sheets module. No storage interface. No live sheet. Do not set `SHEET_ID` or credentials. Do not call Gemini.
- Photos, the dashboard, and Postgres stay out.

## File structure

| Path | Responsibility |
|---|---|
| `api/app/storage.py` | `toggle_supplement(book, date, item) -> dict \| None` |
| `api/app/main.py` | `POST /supplements/toggle` |
| `api/tests/test_api.py` | One full-day flow |

No new module. `PUT /days/{date}`, `PUT /nutrition/{date}`, `POST /supplement-items`, `POST /context-notes`, and `GET /daily-view/{date}` stay as they are.

---

### Task 1: Full-day log and checklist tap

**Files:**
- Modify: `api/app/storage.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_api.py`

**Interfaces:**
- Consumes: `insert_row`, `delete_row`, `upsert_by_date`, `Missing`, `DATE_RE`
- Produces: `toggle_supplement(book: Book, date: str, item: str) -> dict[str, str] | None`. `None` means the row for that date and item was deleted. A dict is the inserted Supplements row, using the checklist item's spelling, `default_dose`, and `unit`. Unknown checklist item raises `Missing`.

- [x] **Step 1: Write the failing test**

Append to `api/tests/test_api.py`:

```python
def test_full_day_log(api):
    client, book = api
    date = "2026-10-21"

    created = client.put(
        f"/days/{date}",
        json={"bodyweight_lb": 180, "sleep_hours": 7.5, "steps": 8000, "summary": "easy day"},
        headers=HEADER,
    )
    assert created.status_code == 200
    day = created.json()
    assert day["date"] == date
    assert day["bodyweight_lb"] == "180"
    assert day["sleep_hours"] == "7.5"
    assert day["steps"] == "8000"
    assert day["summary"] == "easy day"

    corrected = client.put(f"/days/{date}", json={"summary": "still easy"}, headers=HEADER)
    assert corrected.status_code == 200
    assert corrected.json()["id"] == day["id"]
    assert corrected.json()["bodyweight_lb"] == "180"
    assert corrected.json()["sleep_hours"] == "7.5"
    assert corrected.json()["steps"] == "8000"
    assert corrected.json()["summary"] == "still easy"
    assert len(book["Days"]) == 1

    fed = client.put(
        f"/nutrition/{date}",
        json={"calories": 2400, "protein_g": 180, "carbs_g": 220, "fat_g": 70},
        headers=HEADER,
    )
    assert fed.status_code == 200
    totals = fed.json()
    assert totals["calories"] == "2400"
    assert totals["protein_g"] == "180"
    assert totals["carbs_g"] == "220"
    assert totals["fat_g"] == "70"

    refed = client.put(f"/nutrition/{date}", json={"protein_g": 185}, headers=HEADER)
    assert refed.json()["id"] == totals["id"]
    assert refed.json()["calories"] == "2400"
    assert refed.json()["protein_g"] == "185"
    assert refed.json()["carbs_g"] == "220"
    assert refed.json()["fat_g"] == "70"
    assert len(book["Nutrition"]) == 1
    assert "Meals" not in book

    item = client.post(
        "/supplement-items",
        json={"item": "Creatine", "default_dose": 5, "unit": "g", "active": True},
        headers=HEADER,
    )
    assert item.status_code == 200
    assert item.json()["active"] == "TRUE"
    assert item.json()["default_dose"] == "5"

    on = client.post("/supplements/toggle", json={"date": date, "item": "creatine"}, headers=HEADER)
    assert on.status_code == 200
    logged = on.json()
    assert logged["date"] == date
    assert logged["item"] == "Creatine"
    assert logged["dose"] == "5"
    assert logged["unit"] == "g"
    assert logged["source"] == "user"

    off = client.post("/supplements/toggle", json={"date": date, "item": "Creatine"}, headers=HEADER)
    assert off.status_code == 204
    assert book["Supplements"] == []

    again = client.post("/supplements/toggle", json={"date": date, "item": "Creatine"}, headers=HEADER)
    assert again.status_code == 200
    assert again.json()["dose"] == "5"
    assert len(book["Supplements"]) == 1

    assert client.post(
        "/supplements/toggle", json={"date": "21-10-2026", "item": "Creatine"}, headers=HEADER
    ).status_code == 400
    assert client.post(
        "/supplements/toggle", json={"date": date, "item": " "}, headers=HEADER
    ).status_code == 400
    assert client.post(
        "/supplements/toggle", json={"date": date, "item": "Fish oil"}, headers=HEADER
    ).status_code == 404

    note = client.post(
        "/context-notes",
        json={"date": date, "text": "slept short", "tags": "sleep"},
        headers=HEADER,
    )
    assert note.status_code == 200
    assert note.json()["text"] == "slept short"
    assert note.json()["tags"] == "sleep"
    assert note.json()["session_id"] == ""

    view = client.get(f"/daily-view/{date}", headers=HEADER)
    assert view.status_code == 200
    body = view.json()
    assert body["bodyweight_lb"] == "180"
    assert body["sleep_hours"] == "7.5"
    assert body["steps"] == "8000"
    assert body["calories"] == "2400"
    assert body["protein_g"] == "185"
    assert body["context"] == "slept short"
    assert body["supplements"] == "Creatine"

    supplements = client.get("/supplements", params={"date": date}, headers=HEADER)
    assert [row["item"] for row in supplements.json()] == ["Creatine"]
    notes = client.get("/context-notes", params={"date": date}, headers=HEADER)
    assert [row["text"] for row in notes.json()] == ["slept short"]
    saved = client.get(f"/days/{date}", headers=HEADER)
    assert saved.json()["summary"] == "still easy"
    assert client.get(f"/nutrition/{date}", headers=HEADER).json()["fat_g"] == "70"
```

- [x] **Step 2: Run the test to verify it fails**

Run: `uv run pytest api/tests/test_api.py::test_full_day_log -v`

Expected: FAIL at `POST /supplements/toggle`. Days and nutrition assertions before it pass. Do not add a route before this run.

Observed: 405. `GET`/`PATCH`/`DELETE /supplements/{key}` already occupy that path shape, so the missing POST is method-not-allowed rather than 404. The failure is still the missing tap.

- [x] **Step 3: Implement the tap**

In `api/app/storage.py`, after `upsert_by_date`:

```python
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
```

In `api/app/main.py`, import `toggle_supplement` from `api.app.storage`. Inside `mount`, before the `for tab, path in PATHS.items()` loop:

```python
@router.post("/supplements/toggle")
def toggle_supplement_log(body: dict = Body(...), book: Book = Depends(get_book)):
    date = str(body.get("date") or "")
    item = str(body.get("item") or "").strip()
    if DATE_RE.fullmatch(date) is None:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    if item == "":
        raise HTTPException(status_code=400, detail="item is required")
    row = toggle_supplement(book, date, item)
    if row is None:
        return Response(status_code=204)
    return row
```

Leave `POST /supplements` as an insert. A duplicate there stays 409.

- [x] **Step 4: Run the suite**

Run: `uv run pytest`

Expected: the new test passes, and the existing suite still passes. No live sheet. No Gemini call.

- [x] **Step 5: Commit**

Do not commit. The session that wrote this plan was told not to.

## Self-review

- Days upsert (bodyweight, sleep, steps, summary), one Nutrition row (four totals, no Meals tab), checklist tap on/off/on with the default dose, and a context note are all in `test_full_day_log`.
- Partial upsert, `0` vs empty, booleans, and kg-on-`weight_lb` stay covered by Phase 0 tests. This plan does not reimplement them.
- Gemini tag suggestion is not in this phase. The client sends tags. A suggestion call waits until a billed `GEMINI_API_KEY` is in use.
- Photos, dashboard charts, Postgres, and a Meals table are out of this plan.
