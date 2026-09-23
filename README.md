# Wakedonalds Backend

## Sprint 1: Cloud Environment Setup (task 1.2)

### What's done
- Django project basics built with Django REST Framework installed, so
  the backend can serve JSON data to a web frontend and/or the mobile
  app (rather than only rendered HTML pages).
- Settings split into local vs. production, so dev and cloud config
  never mix on accident:
  - `wakedonalds/settings/base.py` — shared settings
  - `wakedonalds/settings/local.py` — SQLite, debug on, zero setup for
    any teammate cloning the repo
  - `wakedonalds/settings/production.py` — MySQL via environment
    variables, debug off, SSL enforced — ready to point at AWS RDS
    once it's provisioned
- All secrets/config (DB credentials, email credentials, allowed
  hosts) are read from environment variables via `python-decouple`,
  never hardcoded. See `.env.example` for the full list.
- `/api/health/` endpoint is live and tested, it checks the database
  connection and returns JSON status. This doubles as the kind of
  endpoint AWS Elastic Beanstalk uses for load balancer health checks.
- `requirements.txt` pinned for local dev and the eventual MySQL/
  gunicorn production setup.
- Other teammates' work (schema, menu UI, cart) just needs a new
  Django app added to `INSTALLED_APPS` — no changes to this config
  required to plug in.

### What's not done yet (next sprint)
- No AWS resources are provisioned yet — no RDS instance, no Elastic
  Beanstalk environment. `production.py` is written and ready to point
  at them the moment they exist.
- No S3/static file storage configured yet.
- No CI/CD (GitHub Actions) for automated deploys yet.

### Running locally
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
Then visit `http://localhost:8000/api/health/` — should return:
```json
{"status": "ok", "service": "wakedonalds-backend", "database": "connected"}
```
