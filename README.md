# Knot: Community Resource-Sharing Platform

Knot lets people share items and micro-rent them, cutting the cost and
waste of buying things you only need occasionally.

**Live demo:** https://knot-jdvl.onrender.com/
(Hosted on a free tier, so the first load can take up to a minute.)

**Demo login:** demo@example.com / YourDemoPassword

## Features
- User authentication, profiles and password reset by email
- Item listings with images
- Booking system with admin approval
- Campaigns and item suggestions
- Payments via PayHero (M-Pesa), running in test mode for the demo

## Tech stack
Python, Django, SQL, HTML/CSS, JavaScript. Deployed on Render.

## Run locally
1. Create and activate a virtual environment: `python -m venv venv`
2. Install dependencies: `pip install -r requirements.txt`
3. Set the environment variables listed below
4. Run `python manage.py migrate`, then `python manage.py runserver`

## Configuration
Secrets are read from environment variables and are not stored in this
repository. See `render.yaml` and `.env.example` for the full list.

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | `True` for local development only |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP account for verification and reset emails |
| `PAYHERO_*` | PayHero payment credentials |
| `PAYHERO_TEST_MODE` | `True` to run payments in test mode |
| `NGROK_URL` | Public URL used for payment callbacks |

## Windows launcher (optional)
`knot_launcher.py` builds a standalone Windows executable with PyInstaller
(see `scripts/build_launcher.ps1`). It runs the Django app locally and keeps
the database and media in folders next to the executable.

## Notes
- The live demo is deployed from a separate private repository.
- Work in progress: moving to a managed Postgres database and adding a demo payment mode

## Author
Sally Munga: [LinkedIn](https://www.linkedin.com/in/sally-munga)

