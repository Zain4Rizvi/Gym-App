# Gym App

One person replaces lift notes, daily macros, supplements, and physique photos with one log. The Expo app in `mobile/` is the phone and the website. The API keeps each account in local files under `data/`.

Read `docs/superpowers/specs/2026-10-21-gym-dashboard-design.md` before changing behavior.

## What exists

- `api/app/storage.py` is the only module that talks to the store. Local accounts and books load and save there. Do not add a storage interface.
- `api/app/main.py` mounts one route set per tab. The tab comes from the path. Close over the sheet name. A route parameter named `tab` becomes a query string, and `POST /exercises?tab=Notes` would write the wrong tab.
- `POST /accounts` and `POST /login` return `{token, email}`. A user token loads that user's book. `AUTH_TOKEN` loads one shared local book. When `SHEET_ID` is set, the API stays on one Google Sheet and one shared token. Accounts do not split a sheet.
- `POST /notes` stores the typed note. It calls Gemini only when `GEMINI_API_KEY` is set. Without that key, `parse_status` stays `pending`. `POST /notes/{id}/parse` returns 503 and `parser not configured`.
- `POST /media` accepts multipart photo bytes and stores them under `data/photos/`. The book keeps `storage_uri` only. `GET /media/{id}/file` streams the bytes for that book.
- `GET /trends` computes top weight, Epley, bodyweight, nutrition, supplement adherence, and weekly muscle volume when read.
- Tests use an in-memory `Book`. `uv run pytest` is the suite. The live sheet test skips unless `SHEET_ID` and `GOOGLE_APPLICATION_CREDENTIALS` are both set.
- Start the API with `uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000`. In `mobile/`, run `npx expo start` and press `w` for the website. A phone on the same Wi-Fi needs `EXPO_PUBLIC_API_URL` set to this PC's LAN address. The default is `http://127.0.0.1:8000`.

## Rules that are already locked

- The typed note is the record. Gemini sees text only. Photos never go to Gemini.
- Dates are `YYYY-MM-DD` from the phone. Timestamps are UTC. Ids are uuid4.
- An empty cell means not recorded. `0` is a real zero. Booleans are `TRUE` and `FALSE`.
- `weight_lb` is canonical. Convert kg only when that write includes `weight_lb` and `unit_entered` is `kg`: `round(weight * 2.2046226218, 2)`.
- Nutrition is one row of daily totals. Add a Meals table only when timing is a question you actually need.
- A correction sets `edited_by_user` and keeps the set row. `Notes.parsed_json` holds the last Gemini payload. There is no audit-log table.
- One note creates one session. The lift screen requires a day label: Push, Pull, Legs, or Other.

## Next

The parser is `api/app/parse.py`. It runs inside `POST /notes` and `POST /notes/{id}/parse` once `GEMINI_API_KEY` is set. Before the first real note is sent, confirm the billed Gemini API terms still say prompts are not used for training. If they do not, use Vertex AI with training disabled.

Postgres, forecasting, significance tests, and factor effects stay out until a later plan. A muscle table waits until a muscle needs its own columns.
