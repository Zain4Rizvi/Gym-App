# Gym App

One person replaces lift notes, daily macros, supplements, and physique photos with one log. The phone app does not exist yet. Phase 0 is a FastAPI service in front of one Google Sheet.

Read `docs/superpowers/specs/2026-10-21-gym-dashboard-design.md` before changing behavior. Phase 0's build steps are in `docs/superpowers/plans/2026-10-21-phase-0-sheet-api.md`.

## What exists

- `api/app/storage.py` is the only module that talks to Sheets. Call functions such as `insert_row` and `upsert_by_date`. Do not add a storage interface.
- `api/app/main.py` mounts one route set per tab. The tab comes from the path. Close over the sheet name. A route parameter named `tab` becomes a query string, and `POST /exercises?tab=Notes` would write the wrong tab.
- Tests use an in-memory `Book`. `uv run pytest` is the suite. The live sheet test skips unless `SHEET_ID` and `GOOGLE_APPLICATION_CREDENTIALS` are both set.
- Preview: `$env:AUTH_TOKEN = "local-dev-token"; uv run uvicorn api.app.main:app --reload`, then open `http://127.0.0.1:8000/docs`. Real writes also need the sheet id and the service-account file. Share the sheet with that account as Editor.
- `POST /notes` requires `client_request_id`, stores `parse_status=pending`, and does not call Gemini. `POST /notes/{id}/parse` returns 503.

## Rules that are already locked

- The typed note is the record. Gemini sees text only. Photos never go to Gemini.
- Dates are `YYYY-MM-DD` from the phone. Timestamps are UTC. Ids are uuid4.
- An empty cell means not recorded. `0` is a real zero. Booleans are `TRUE` and `FALSE`.
- `weight_lb` is canonical. Convert kg only when that write includes `weight_lb` and `unit_entered` is `kg`: `round(weight * 2.2046226218, 2)`.
- Nutrition is one row of daily totals. Add a Meals table only when timing is a question you actually need.
- A correction sets `edited_by_user` and keeps the set row. `Notes.parsed_json` holds the last Gemini payload. There is no audit-log table.
- One note creates one session. The lift screen requires a day label: Push, Pull, Legs, or Other.

## Next

Phase 1 is the lift-note parser. Write a new plan under `docs/superpowers/plans/` before coding. Done when the Sep 22 Push note and a longer note both parse. Those notes are not in the repo yet. Ask for them before writing the acceptance fixtures.

Before the first real note is sent, confirm the billed Gemini API terms still say prompts are not used for training. If they do not, use Vertex AI with training disabled.

After that: Phase 2 daily log, Phase 3 photos in a private bucket, Phase 4 dashboard, Phase 5 Postgres by replacing `storage.py` only.
