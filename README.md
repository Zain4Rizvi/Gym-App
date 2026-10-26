# Gym App

One local log. The website is the Expo app in `mobile/`. Notes, trends, coach, and account are the screens. The API stores each account in `data/` on this machine.

```powershell
uv run uvicorn api.app.main:app --host 0.0.0.0 --port 9477
```

```powershell
cd mobile
npx expo start
```

Press `w` for the website. A phone on the same Wi-Fi needs `EXPO_PUBLIC_API_URL` set to this PC's LAN address before `npx expo start`. The default is `http://127.0.0.1:9477`.

Open the book signs in as the demo account. `POST /notes` keeps the typed text and parses it when `GROQ_API_KEY` or `GEMINI_API_KEY` is set. Without a key the note stays `pending`, and `POST /notes/{id}/parse` returns 503 with `parser not configured`.

```powershell
uv run pytest
```

`GET /health` needs no token. Every other data route sends `Authorization: Bearer <token>`.
