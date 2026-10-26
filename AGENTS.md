# Gym App

One person logs lifts in a note. The Expo app in `mobile/` is the phone and the website. The API keeps each account in local files under `data/`.

## What exists

- `api/app/storage.py` is the only module that talks to the store. It loads and saves accounts and JSON books. Do not add a storage interface.
- A book has Notes, Sessions, Sets, Exercises, and Aliases. On load, other keys in an old file are ignored. On save, only those five tabs are written.
- `POST /login` returns `{token, email}`. A user token loads that user's book. The app opens the demo account. `register_account` creates that account inside the API. There is no signup route.
- `POST /notes` stores the typed note. It calls the parser only when `GROQ_API_KEY` or `GEMINI_API_KEY` is set. Without a key, `parse_status` stays `pending`. `POST /notes/{id}/parse` returns 503 and `parser not configured`.
- `GET /trends` computes top weight and Epley when read. Bodyweight and nutrition stay empty. Supplement days stay 0. Day count is the number of distinct session dates.
- `POST /coach` answers from the book text. It does not change the book.
- Tests use an in-memory `Book`. `uv run pytest` is the suite.
- Start the API with `uv run uvicorn api.app.main:app --host 0.0.0.0 --port 9477`. In `mobile/`, run `npx expo start` and press `w` for the website. A phone on the same Wi-Fi needs `EXPO_PUBLIC_API_URL` set to this PC's LAN address. The default is `http://127.0.0.1:9477`.

## Rules that are already locked

- The typed note is the record. The model sees text only.
- Dates are `YYYY-MM-DD` from the phone. Timestamps are UTC. Ids are uuid4.
- An empty cell means not recorded. `0` is a real zero. Booleans are `TRUE` and `FALSE`.
- `weight_lb` is canonical. Convert kg only when that write includes `weight_lb` and `unit_entered` is `kg`: `round(weight * 2.2046226218, 2)`.
- A correction sets `edited_by_user` and keeps the set row. `Notes.parsed_json` holds the last model payload. There is no audit-log table.
- One note creates one session.

## Next

The parser is `api/app/parse.py`. It runs inside `POST /notes` and `POST /notes/{id}/parse` once a model key is set. Before the first real note is sent, confirm the billed API terms still say prompts are not used for training. If they do not, use a host with training disabled.

Postgres, forecasting, significance tests, and factor effects stay out until a later plan.
