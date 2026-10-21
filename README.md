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
