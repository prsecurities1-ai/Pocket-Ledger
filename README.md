# PocketLedger

PocketLedger is a personal expense tracker built with Django and SQLite. Track income and expenses, manage budgets, and review spending from a responsive dashboard.

## Features

- User registration, login, and account-specific financial data
- Income and expense transactions with create, edit, and delete actions
- Built-in and custom categories
- Monthly overall and category budgets
- Balance and monthly income/expense summaries
- Six-month cash-flow and monthly category-spending charts
- Transaction search, type/category filters, and date ranges
- Per-account USD ($) or INR (₹) display preference
- Persistent dark/light theme preference
- Responsive interface with Bootstrap 5 and Bootstrap Icons
- SQLite persistence, Django form validation, and CSRF-protected forms
- WhiteNoise static-file serving for WSGI deployments

Currency selection changes the displayed symbol; it does not convert or alter stored amounts.

## Requirements

- Python 3.12 or newer
- pip

Python dependencies are listed in [`requirements.txt`](requirements.txt).

## Run locally

From the project root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies, apply migrations, and start Django:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and create an account. SQLite data is stored in `db.sqlite3` at the project root.

To create an administrator account for Django admin:

```bash
python manage.py createsuperuser
```

## Tests and checks

Run the app tests and Django system checks with:

```bash
python manage.py test pocketledgerapp
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Gunicorn and static files

Gunicorn serves the Django WSGI application. WhiteNoise serves compressed static assets after Django's `collectstatic` command.

For a local Gunicorn smoke test, run these commands in separate terminals:

```bash
python manage.py collectstatic --noinput
gunicorn pocketledger.wsgi:application --bind 127.0.0.1:8001
```

Then check the application and assets:

```bash
curl -I http://127.0.0.1:8001/
curl -I http://127.0.0.1:8001/static/pocketledgerapp/style.css
curl -I http://127.0.0.1:8001/static/pocketledgerapp/main.js
```

Each request should return `HTTP/1.1 200 OK`.

## Render deployment notes

Use the following commands in the Render web service configuration:

**Build command**

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

**Start command**

```bash
gunicorn pocketledger.wsgi:application --bind 0.0.0.0:$PORT
```

Before exposing this project publicly, update `pocketledger/settings.py` for production: turn off `DEBUG`, load a secret key from a protected environment variable, and set `ALLOWED_HOSTS` to the deployed hostname(s). The checked-in settings currently use development values and are not production-ready.

Render's local filesystem is ephemeral unless a persistent disk is configured. Since this project uses SQLite, configure a persistent disk and place `db.sqlite3` on it if database data must survive redeploys or restarts. For a multi-instance production deployment, use a managed database instead of SQLite.
