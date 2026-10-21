# Gym Dashboard Design

Date: 2026-10-21

One app replaces four: lift notes, physique photos, macro totals, and supplements. It starts as a fast logger and a trend dashboard. Records are structured from day one so later analysis (lift forecasting, significance tests, factor effects) does not require a rewrite.

This is the product spec. The first implementation plan covers Phase 0 only.

## Changes from the draft

These are locked. The rest of this document is the spec.

1. **Nutrition is one row per date:** calories, protein, carbs, fat. A Meals table is added only when a question actually needs timing, such as pre-workout carbs.
2. **Corrections are the set row plus the last parse.** `Sets.edited_by_user` marks a row a person changed. `Notes.parsed_json` keeps the last Gemini payload. There is no audit-log table.
3. **A retried save is the same note.** `Notes.client_request_id` is unique. The same id returns the existing note.
4. **Parse stays inside the request.** The API writes the note, calls Gemini, writes sets, then responds. Cloud Run throttles CPU after the response, so a background parse would die. The note row is on the sheet before Gemini is called. `POST /notes/{id}/parse` runs that same parse again.
5. **The lift screen requires a day label** (Push, Pull, Legs, Other). The user can change it. One note creates one session. A note that contains two workouts is split by the user before save.
6. **Checklist items live in `SupplementItems`.** Log rows live in `Supplements`.
7. **Storage is one module of functions.** It is the only code that talks to Sheets. Tests use an in-memory sheet. There is no storage interface with a single implementation.
8. **Estimated 1RM is Epley, computed when read, never stored:** `weight_lb * (1 + reps / 30)`, working sets that have weight and reps.
9. **Muscle lists stay comma-separated** on the exercise row. Split them into a table when weekly volume by muscle is built.

## Principles

1. **Day-indexed.** Logged rows join to a date. Sets join through their session. Exercises, Aliases, and SupplementItems are catalogs and have no date.
2. **Raw input is truth.** Lift notes are stored as typed. Gemini's interpretation is a regenerable layer on top.
3. **Everything logged is editable.** A correction updates the row and sets `edited_by_user` when the row is a set. It is not a silent overwrite of a Gemini row.
4. **Gemini sees text only.** Photos never enter the Gemini path.
5. **Sheets is the MVP store.** It sits behind the storage module so a later Postgres swap replaces that module.

## Decisions

| Topic | Decision |
|---|---|
| Users | One person, one Google Sheet |
| Platforms | Expo app for iOS and Android. Website in Phase 4 |
| Storage | Google Sheets now. Postgres in Phase 5, by replacing the storage module |
| Offline | No queue. The app requires a connection. The unsent lift-note text is kept on the phone |
| Units | Pounds unless the note says kg. Kg is converted on entry |
| Auth | One shared bearer token |
| Confidentiality | Photos go to a private bucket. The sheet stores metadata only |
| Parse quality | The Sep 22 Push note is the first eval, once pasted. A longer real note is the second |
| Macros | One row of daily totals |
| Time | The phone sends the calendar date. Timestamps are UTC. The server does not guess a timezone |
| Gemini | A current Flash model via the Gemini API, structured JSON. Model id comes from `GEMINI_MODEL`, default `gemini-2.5-flash` |

## Architecture

```
Phone ──► API ──► storage module ──► Sheet (later Postgres)
           │
           ├──► Gemini (text fields only)
           └──► Private photo bucket (never Gemini)
```

- **Phone (Expo).** Four entry points: Add Lift Notes, Add Daily Log, Take Physique Pic, Dashboard. Not built in Phase 0.
- **API (FastAPI).** Holds every secret. Deploys to Cloud Run.
- **Storage module.** The only code that imports the Sheets client. Callers use functions such as `save_sets(session_id, sets)`.
- **Parser module (Phase 1).** Input is `raw_text`, `day_label`, and the exercise catalog with aliases. The input type has no file or image field.
- **Photo module (Phase 3).** Writes bytes to a private Cloud Storage bucket and a Media row to the sheet. It does not import the parser module or the Gemini client.

Privacy is structural. A test in Phase 1 fails if the parser input grows a file field. A test in Phase 3 fails if the photo module imports the Gemini client.

Before the first real note is sent, confirm the current Gemini API terms for a billed project still say prompts are not used for training. If the terms allow training on prompts, switch the parser to Vertex AI with training disabled before any note is sent. Lift notes and context notes are the payload.

### Layout

```
api/
  app/main.py        # routes
  app/auth.py        # bearer check
  app/storage.py     # only Sheets code
  app/schema.py      # tab names and headers
  tests/             # in-memory sheet
```

Phase 1 adds `api/app/parse.py`. Phase 3 adds `api/app/photos.py`. The Expo app is a later sibling, `mobile/`.

### Secrets

| Name | When |
|---|---|
| `AUTH_TOKEN` | Phase 0 |
| `SHEET_ID` | Phase 0 |
| `GOOGLE_APPLICATION_CREDENTIALS` | Phase 0, service account file |
| `GEMINI_API_KEY` | Phase 1 |
| `GEMINI_MODEL` | Phase 1, default `gemini-2.5-flash` |
| `PHOTO_BUCKET` | Phase 3 |

The sheet is shared with the service account email. The container Python matches `pyproject.toml` (3.14).

## Data model

Every tab except DailyView has `id`, `created_at`, `updated_at`, and `source`. `id` is a uuid4 string. Timestamps are ISO 8601 UTC. Dates are `YYYY-MM-DD` from the phone. `source` is `gemini`, `user`, or `import`.

The storage module reads and writes by header name. Column order does not matter. Unknown columns are ignored, so a later micro column does not break writes.

Empty cell means not recorded. The number 0 is a real zero, never a stand-in for missing. Booleans are `TRUE` or `FALSE`.

| Tab | Grain | Columns beyond the common four |
|---|---|---|
| Days | One per date | `date`, `bodyweight_lb`, `sleep_hours`, `steps`, `day_label`, `summary` |
| Notes | One raw lift note | `session_date`, `day_label`, `raw_text`, `parse_status`, `error_text`, `model`, `prompt_version`, `parsed_json`, `client_request_id` |
| Sessions | One workout | `date`, `start_time`, `end_time`, `label`, `note_id`, `session_notes` |
| Sets | One set | `session_id`, `note_id`, `exercise_id`, `name_as_written`, `set_number`, `weight_lb`, `unit_entered`, `reps`, `rpe`, `set_type`, `variation`, `needs_review`, `edited_by_user` |
| Exercises | Catalog | `canonical_name`, `movement_pattern`, `equipment`, `primary_muscles`, `secondary_muscles`, `status` |
| Aliases | Many per exercise | `alias`, `exercise_id`, `day_label` |
| Nutrition | One per date | `date`, `calories`, `protein_g`, `carbs_g`, `fat_g` |
| SupplementItems | Checklist config | `item`, `default_dose`, `unit`, `active` |
| Supplements | One item per date | `date`, `item`, `dose`, `unit` |
| ContextNotes | Per day or session | `date`, `session_id`, `text`, `tags` |
| Media | Metadata only | `date`, `pose`, `storage_uri`, `taken_at` |
| DailyView | Script output | `date`, `day_label`, `bodyweight_lb`, `sleep_hours`, `steps`, `calories`, `protein_g`, `top_lifts`, `context`, `supplements` |

Unique keys:

- Days and Nutrition: `date`
- Supplements: (`date`, `item`)
- Aliases: (`alias` casefolded, `day_label`), where a blank `day_label` means any day
- Notes: `client_request_id` when present
- Exercises: `canonical_name`, case-insensitive
- SupplementItems: `item`, case-insensitive

Enums:

- `parse_status`: `pending`, `done`, `error`
- `set_type`: `warmup`, `working`, `drop`, `failure`, or empty
- Exercise `status`: `active`, `proposed`
- `day_label`: `Push`, `Pull`, `Legs`, `Other`, or empty on a day that has no lifting
- Context `tags`: comma-separated from `sleep`, `illness`, `stress`, `travel`
- `pose`: `front`, `side`, `back`

`primary_muscles` and `secondary_muscles` are comma-separated canonical names. `ponytail:` split into a muscle table when volume-by-muscle is built.

`weight_lb` is canonical. `unit_entered` is `lb` or `kg`. Kg converts with `weight * 2.2046226218`, rounded to 2 decimal places. A note that does not say kg is pounds.

`rpe`, `set_type`, and `variation` are filled only when the note states them. `"@8"` is RPE 8. `"warmup"` is `set_type`. Gemini does not guess. A reps token that is not a number (for example AMRAP) leaves `reps` empty and sets `needs_review`.

Estimated 1RM, volume, and tonnage are not columns. Phase 4 computes Epley at read time.

Aliases are rows. A day-specific alias beats a blank-day alias. Exercise identity for joins is `exercise_id`. `name_as_written` is display and audit only.

A day can hold more than one session. Alias scope and the session `label` use that note's `day_label`. `Days.day_label` is the daily-log value. DailyView joins the session labels for that date.

Writes are partial upserts. A field absent from the request stays as stored. A field sent as null is cleared. `PUT` by date and `PATCH` by id both follow this rule.

DailyView is rewritten by `rebuild_daily_view()` after a write. It is not a formula tab. `top_lifts` is a display string such as `Bench Press 225x5`. `ponytail:` full-tab rewrite is fine for one user; switch to a single-date update if it gets slow.

## Lift-note flow

1. The user types the note, sets the day label and the date (default today), and taps Save. Save stays disabled while the request is in flight. The phone keeps the unsent text locally and clears it when the save returns.
2. `POST /notes` requires `client_request_id`. A missing id is 400. The API inserts the Notes row with `parse_status=pending`. Phase 1 then calls Gemini with `raw_text`, `day_label`, and the catalog (exercises plus aliases). Phase 0 returns after the insert.
3. On success the API writes one Session (`date`, `label` from the note, `note_id`) and its Sets, stores the Gemini body in `parsed_json`, and sets `parse_status=done`. `start_time`, `end_time`, and `session_notes` stay empty unless the note states them. Zero sets is a failure. On failure it sets `parse_status=error` and `error_text`, and writes no session and no sets.
4. The response is the note plus its sets, including when parse failed. The save itself succeeded. HTTP 200.
5. The same `client_request_id` on `POST /notes`, when the note is `done`, returns that note and does not parse again. When it is `pending` or `error`, Phase 1 runs the parse. Phase 0 returns the stored note.
6. Review is optional. `needs_review` is true when the name was unknown or the model was unsure. The user can fix the exercise, weight, reps, RPE, or set type. A correction updates the set and sets `edited_by_user`. Assigning a written name to an exercise also creates an alias from `name_as_written` to that `exercise_id`, scoped to the note's day label. A weight or reps fix does not create an alias.

Prompt rules: use the day label to disambiguate, map known aliases, keep `name_as_written`, set `needs_review` when unsure, never merge or invent a movement to force a match, never fabricate RPE or set type. `prompt_version` starts at `v1`.

Unknown name: create an Exercise with `status=proposed`, `canonical_name` equal to the trimmed written name, and `needs_review` on the set. Do not attach it to a different movement.

Re-parse is `POST /notes/{id}/parse`. It reuses the session for that note when one already exists. One note has one session.

- Call Gemini first. Compare the new sets to rows that must be kept: `edited_by_user` true, or `source` other than `gemini`.
- A conflict is a kept row with the same `set_number` and the same `name_as_written` (casefolded) as a new set, where `weight_lb`, `reps`, `rpe`, or `set_type` differ.
- On any conflict, write nothing. The response lists the conflicts. The client sends `overwrite_set_ids` on a second call to replace those rows (`source=gemini`, `edited_by_user` cleared). Ids left out stay as the user saved them.
- With no conflict, delete sets for that note where `source=gemini` and `edited_by_user` is false, then insert new sets that do not match a kept row on `set_number` plus `name_as_written`. A kept row whose values already match the new set stays as it is.

Acceptance, once the note is pasted to `tests/fixtures/sep22_push.txt`:

- Day label Push.
- Catalog contains incline dumbbell press with alias `Incline Dumbell` scoped to Push, and a curl alias for the same words scoped to Pull.
- Result: three exercises, two sets each, `unit_entered=lb`, weights stored in `weight_lb`.
- The same written name on a Pull day resolves through the Pull alias.

The second eval is the longer note, fixture plus expected JSON, added when it is pasted. Phase 1 is not done until both pass.

## Other daily inputs

- **Bodyweight, sleep, steps, day summary:** one Days upsert per date.
- **Macros:** one Nutrition upsert per date. No meal rows. No micro columns until a micro is named.
- **Supplements:** `SupplementItems` is the checklist (creatine and so on). A tap on an item with no row today inserts a Supplements row with the default dose. A tap on an item that already has a row today deletes that row.
- **Context notes:** free text plus optional tags. Gemini may suggest tags from the text. That call is text only.
- **Physique pics:** camera bytes go to the private bucket. The sheet receives a Media row. Pose is `front`, `side`, or `back`.

## HTTP

All routes require `Authorization: Bearer <AUTH_TOKEN>`. A mismatch is 401. Comparison is constant-time.

The API mirrors the storage functions. Phase 0 routes:

- `GET /health` with no auth
- Days, Nutrition: `GET` and `PUT` by date
- Notes: `POST`, `GET /notes/{id}`, `POST /notes/{id}/parse`
- Sessions and Sets: `GET` by id and by date, `PATCH` a set, `DELETE` a set
- Exercises, Aliases, SupplementItems: `GET`, `POST`
- Supplements, ContextNotes, Media: `GET` by date, `POST`, `DELETE` by id
- `POST /daily-view/rebuild`

Every row tab also supports `GET`, `PATCH`, and `DELETE` by id. Phase 0 `POST /notes` stores `pending` and does not call Gemini. `POST /notes/{id}/parse` without `GEMINI_API_KEY` returns 503 and leaves the note unchanged. Phase 1 runs the parser inside `POST /notes` and on the parse route. Phase 3 accepts photo bytes on `POST /media`.

A live sheet test runs only when `SHEET_ID` and credentials are set. The default test suite uses the in-memory sheet.

Delete removes the row. The raw note is kept when a set is deleted.

## Dashboard

Phase 4 reads the same storage functions and charts them. Charts start once a few weeks of clean data exist.

- **Lifts:** top set and Epley 1RM per exercise over time. Weekly volume by muscle group once muscles are split out.
- **Body:** bodyweight with a 7-day moving average.
- **Nutrition and supplements:** calories and protein against bodyweight. Supplement adherence is logged days over checklist days.
- **Day view:** one date shows days, sessions, sets, nutrition, supplements, context, and media metadata.

## Phases

| Phase | Scope | Done when |
|---|---|---|
| 0 | Tabs, storage module, bearer token, Cloud Run | A client with the token can read and write every tab, and DailyView rebuilds. Tests use the in-memory sheet |
| 1 | Lift-note screen, Gemini parse, review, alias learning, session list | Sep 22 fixture and the long-note fixture pass. Training-off is confirmed before the first real note |
| 2 | Daily log: bodyweight, macros, supplements, context | A full day logs in under a minute |
| 3 | Physique photos to the private bucket | A photo is stored and the photo module has no Gemini import |
| 4 | In-app dashboard, then the website | Trend charts on real data |
| 5 | Postgres and accounts, then forecasting, significance, and factor effects | The swap touches the storage module only |

## Out of scope

- Offline queue
- Food logger and MyFitnessPal import (an import can land later as `source=import`)
- Accounts, multi-user, and sharing
- Stored 1RM, volume, or tonnage
- Meal-level nutrition
- A muscle junction table, until volume-by-muscle is built
- An edit history table
