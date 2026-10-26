# Gym App

One local log for lift notes, a daily check-in, physique photos, and trends. The API stores each account in `data/` on this machine. The Expo app in `mobile/` is the phone app and the website.

```powershell
uv run uvicorn api.app.main:app --host 0.0.0.0 --port 9477
```

```powershell
cd mobile
npx expo start
```

Press `w` for the website. A phone on the same Wi-Fi needs `EXPO_PUBLIC_API_URL` set to this PC's LAN address before `npx expo start`. The default is `http://127.0.0.1:9477`.

Create an account in the app. No `AUTH_TOKEN`, sheet id, or Gemini key is required to log. `POST /notes` keeps the typed text and parses it when `GEMINI_API_KEY` is set. Without that key the note stays `pending`, and `POST /notes/{id}/parse` returns 503 with `parser not configured`.

```powershell
uv run pytest
```

Tests use an in-memory workbook. The live sheet test skips unless `SHEET_ID` and `GOOGLE_APPLICATION_CREDENTIALS` are both set.

`AUTH_TOKEN` still opens one shared local book. When `SHEET_ID` is set, the API keeps the one-sheet, one-token path. Share that sheet with the service account as Editor.

Cloud Run can host the sheet API later:

```powershell
gcloud secrets create gym-sheets-sa --data-file=PATH_TO_SA.json
$projectNumber = gcloud projects describe (gcloud config get-value project) --format="value(projectNumber)"
gcloud secrets add-iam-policy-binding gym-sheets-sa --member="serviceAccount:${projectNumber}-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
gcloud run deploy gym-api --source . --region us-east1 --allow-unauthenticated --timeout=60 --set-env-vars "SHEET_ID=YOUR_SHEET_ID,AUTH_TOKEN=YOUR_TOKEN,GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json" --set-secrets "/secrets/sa.json=gym-sheets-sa:latest"
```

`GET /health` needs no token. Every other data route sends `Authorization: Bearer <token>`.
