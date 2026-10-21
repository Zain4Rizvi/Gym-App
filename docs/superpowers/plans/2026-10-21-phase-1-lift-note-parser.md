# Phase 1 Lift-Note Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse a stored lift note into one session and its set rows, through an injectable model client, and keep the typed note when parsing fails.

**Architecture:** `api/app/parse.py` turns a model JSON payload into Sessions and Sets by calling `insert_row`, `patch_row`, and `delete_row`. `POST /notes` still inserts `parse_status=pending` before any model call. When a model is injected (or `GEMINI_API_KEY` is set), that request then parses. `POST /notes/{id}/parse` runs the same function. Tests pass a fake callable and an in-memory `Book`. No test opens a socket.

**Tech Stack:** Python 3.14, uv, FastAPI, pytest, stdlib `urllib` for the live Gemini call. No new dependency.

Spec: `docs/superpowers/specs/2026-10-21-gym-dashboard-design.md`

I'm using the writing-plans skill to create this plan.

## Global Constraints

- The typed note is the record. The model sees `raw_text`, `day_label`, and the exercise/alias catalog. No file or image field.
- Dates are `YYYY-MM-DD`. Timestamps are UTC. Ids are uuid4. The parser does not read the header date; `Notes.session_date` is the session date.
- Empty cell means not recorded. `0` is a real zero. Booleans are `TRUE` and `FALSE`.
- `weight_lb` is canonical. Convert kg only when that write includes `weight_lb` and `unit_entered` is `kg`: `round(weight * 2.2046226218, 2)`, via existing `canonicalize_weight`.
- One note, one session. Day label is `Push`, `Pull`, `Legs`, or `Other`.
- `parse_status` is `pending`, `done`, or `error`. `prompt_version` is `v1`. Model id is `GEMINI_MODEL` or `gemini-2.5-flash`.
- `source` for parsed sessions, sets, and proposed exercises is `gemini`. A user correction sets `edited_by_user` to `TRUE`.
- Unknown written name: create an Exercise with `status=proposed` and `canonical_name` equal to the trimmed written name. Do not attach it to a different movement. `needs_review` is true.
- Zero sets is a failure. On model failure set `parse_status=error` and `error_text`, and do not write a session or sets. Do not change `raw_text`.
- Re-parse reuses the session. Kept rows are `edited_by_user=TRUE` or `source` other than `gemini`. A conflict is the same `set_number` and casefolded `name_as_written` where `weight_lb`, `reps`, `rpe`, or `set_type` differ. With no `overwrite_set_ids`, write nothing and list conflicts. With that list, replace those rows (`source=gemini`, `edited_by_user` cleared) and leave the other kept rows. Then delete `source=gemini` and not edited, and insert new sets that do not match a kept row.
- `POST /notes` with the same `client_request_id` returns the stored note. If it is `done`, do not parse again. If it is `pending` or `error` and a model is available, parse.
- Without a model, `POST /notes/{id}/parse` is 503 and the note is unchanged. `storage.py` stays the only Sheets module. No storage interface.
- Paid Gemini API terms (Additional Terms, effective March 23, 2026) say Google does not use paid-service prompts or responses to improve products. Unpaid quota does. `GEMINI_API_KEY` must be a billed project. This plan does not send a note. Tests never call `urlopen`.
- Do not commit in the session that was told not to commit.

## Corpus

There is no Sep 22 note. Do not invent one. Zain pasted nine October notes. Each block is one note and one session. The word after the date is the day label. The sheet date is that calendar day in 2026 (`Oct 9` → `2026-10-09`). Store the block verbatim in `api/tests/fixtures/`.

Checked parses: `2026-10-10-push.txt` (shorter) and `2026-10-15-legs.txt` (longest). Messy tokens from the other notes are a mapping test, not a fake Sep 22 fixture.

## Choices the spec leaves open

- Model JSON is `{exercises: [{name_as_written, sets: [{weight, reps, unit, rpe, set_type, variation, unsure}]}], start_time, end_time, session_notes}`. `parsed_json` stores that body.
- A weight or reps token that is not a plain number (`80 ish`, `70 z`, `i op`, `6?`, `AMRAP`) is stored empty and `needs_review=TRUE`. The digits inside the token are not guessed.
- Weight present and reps empty (trailing `x`) is `needs_review`. Both empty (name with no sets) is one set row, not a dropped exercise, and `needs_review`. Reps present and weight empty (a pull-up) is not a review by itself.
- `@8` stores RPE `8`. `warmup` / `working` / `drop` / `failure` store `set_type`. Anything else in those slots is empty and `needs_review`.
- A line like `And 130, 130` is not joined to the previous exercise. The model transcribes the line; the mapper does not invent the link.
- Conflict JSON is `{set_id, name_as_written, set_number, fields}` on HTTP 200. Omitted `overwrite_set_ids` means write nothing. A list, including an empty one, means apply the overwrite and still write the non-conflicting sets.
- If an alias for that written name and day label already exists, a correction does not replace it.

## File structure

| Path | Responsibility |
|---|---|
| `api/app/parse.py` | Model input, live Gemini call, payload mapping, re-parse, alias on correction |
| `api/app/main.py` | `get_model`, parse inside `POST /notes` and `POST /notes/{id}/parse`, set corrections |
| `api/tests/test_parse.py` | Fake model, October notes, messy tokens, kg/0, conflicts |
| `api/tests/fixtures/2026-10-*.txt` | Verbatim notes |

---

### Task 1: Verbatim fixtures

**Files:**
- Create: `api/tests/fixtures/2026-10-09-pull.txt` through `2026-10-20-push.txt` (nine files, no Oct 12, 17, or 18)

**Interfaces:**
- Consumes: the pasted notes
- Produces: file text equal to the typed `raw_text`

- [x] **Step 1:** Write each block exactly as pasted, one file per date, UTF-8, trailing newline.

- [x] **Step 2:** Do not add `sep22_push.txt`.

### Task 2: Mapper and parse route

**Files:**
- Create: `api/app/parse.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_parse.py`

**Interfaces:**
- Consumes: `insert_row`, `patch_row`, `delete_row`, `get_row`, `apply_fields`, `Book`
- Produces:
  - `model_input(note, book) -> dict` with keys `raw_text`, `day_label`, `catalog`
  - `configured_model() -> Callable | None`
  - `gemini_complete(info: dict) -> dict` (live; tests must not call it)
  - `run_parse(book, note, model, overwrite_set_ids: list | None) -> dict` returning `{note, sets, conflicts}`
  - `learn_alias(book, set_row) -> None`
  - `get_model()` dependency in `main.py`

- [x] **Step 1: Write the failing tests**

`api/tests/test_parse.py` uses the same in-memory `get_book` override as `api/tests/test_api.py`, deletes `GEMINI_API_KEY`, and replaces `urllib.request.urlopen` with a function that raises `AssertionError("live Gemini call")`.

Cover:

1. Oct 10 Push via `POST /notes` with a fake. Five sets, one session dated `2026-10-10` labeled `Push`, pounds, Pushdown reps empty and `needs_review=TRUE`, the other sets `FALSE` when those names are already in the catalog. `raw_text` equals the fixture. A second `POST /notes` with the same `client_request_id` does not call the fake again. Model input keys are exactly `raw_text`, `day_label`, `catalog`.
2. Oct 15 Legs via insert-while-unconfigured (stays `pending`) then `POST /notes/{id}/parse`. Twelve sets, one session, Leg extension second set weight `250`, reps empty, `needs_review=TRUE`. A second parse keeps one session and twelve sets.
3. Messy tokens from the corpus, through the parse route: `80 ish`, `70 z`, `i op`, `6?`, `Pusjdown`, trailing `x`, and a name with no sets. Uncertain numbers are empty, not `0`. `Pusjdown` becomes its own `proposed` exercise, not Pushdown. The set row is kept.
4. Synthetic note (not a real day): `20` kg → `44.09`, weight `0` stays `0`, `@8` → RPE `8`, `warmup` stays, `AMRAP` → empty reps and `needs_review`.
5. Alias `Incline dumbell` on Push and Pull resolves to different exercises.
6. User patch of a set sets `edited_by_user=TRUE`. Re-parse that disagrees lists conflicts and writes nothing. `overwrite_set_ids` replaces that row and clears the flag. A weight patch does not create an alias; assigning `exercise_id` does, scoped to the note's day label.
7. A raising fake on `POST /notes` returns HTTP 200, `parse_status=error`, the same `raw_text`, and no session or sets. The same `client_request_id` with a working fake then parses.
8. `configured_model()` is `None` without `GEMINI_API_KEY` and is `gemini_complete` with a key. The test does not call it.

Run: `uv run pytest api/tests/test_parse.py -v`

Expected before implementation: import or attribute errors.

- [x] **Step 2: Implement `api/app/parse.py`**

`plan_sets` walks `exercises`. An empty `sets` list becomes one blank set. `set_number` starts at 1 inside each exercise. Plain numbers match `^(?:0|[1-9]\d*)(?:\.\d+)?$` after strip; integer-valued numbers store without a decimal. Non-numbers store `""` and flag review. Missing unit with a weight means `lb`.

`run_parse` calls the model with `model_input` first. Planning or model exceptions patch the note to `error` and return. Conflict detection happens before any session, exercise, or set write. Unknown names are flagged before any proposed exercise is inserted, so a second set of the same new name stays `needs_review`.

`gemini_complete` POSTs text to `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with `responseMimeType=application/json` and header `x-goog-api-key`. Timeout 30s. Comment: the key must be a billed project; unpaid quota is trained on. No retry.

- [x] **Step 3: Wire `api/app/main.py`**

`get_model` returns `configured_model()`. `POST /notes` parses when a model exists and the note is not `done`. `POST /notes/{id}/parse` returns 503 when `model is None` (detail `parser not configured`) after loading the note. Optional JSON body `overwrite_set_ids`. `PATCH /sets` forces `edited_by_user=true` and calls `learn_alias` only when the body includes `exercise_id`.

- [x] **Step 4: Run the suite**

Run: `uv run pytest`

Expected: existing tests still pass, including `test_notes_stay_pending_and_parse_does_not_touch_them` and `test_app_source_does_not_import_gemini`. New parse tests pass. No live Gemini call.

- [x] **Step 5: Commit**

Do not commit when the current instruction says not to. Otherwise:

```bash
git add api/app/parse.py api/app/main.py api/tests/test_parse.py api/tests/fixtures docs/superpowers/plans/2026-10-21-phase-1-lift-note-parser.md
git commit -m "Parse lift notes into sessions and sets."
```

## Self-review

- Spec parse flow, re-parse conflicts, unknown names, alias learning, kg, empty vs 0, RPE, set type, and text-only input each have a test.
- Sep 22 is absent on purpose. October 10 and October 15 replace that acceptance pair for this corpus.
- No Meals table, photo bucket, dashboard, or Postgres.
- `POST /notes` without a model stays pending, so Phase 0 tests stay valid.
