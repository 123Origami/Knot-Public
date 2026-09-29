# Knot Project Submission

This repository includes a standalone Windows launcher build for submission.

## What to submit

Submit the executable at `dist/knot-launcher.exe`.

If the upload platform expects a zip file, include these files:

- `dist/knot-launcher.exe`
- `.env.example`
- this `README.md`

## Secrets and configuration

Do not hardcode secrets in the executable or repository files.

Set these values in environment variables on the target machine:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `PAYHERO_USERNAME`
- `PAYHERO_API_KEY`
- `PAYHERO_API_SECRET`
- `PAYHERO_WEBHOOK_SECRET`
- `PAYHERO_ACCOUNT_NUMBER`
- `PAYHERO_CHANNEL_ID`
- `NGROK_URL`
- `PAYHERO_TEST_MODE`

## Build notes

The launcher is built with PyInstaller and starts the Django app directly.
It keeps the database, media files, and static output in writable folders next
to the executable so the app can run without exposing credentials.