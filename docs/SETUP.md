# Setup Guide (Local Development, VS Code)

## Prerequisites
- Python 3.10 or newer
- Git
- VS Code with the Python extension installed

## 1. Clone or open the project
If you already have the folder locally, open it in VS Code:
```
code link-shortener
```

If cloning from your GitHub repo (see docs/GITHUB_SETUP.md for the
initial upload), pull it down with:
```
git clone https://github.com/AriyaSrfZ/link-shortener.git
cd link-shortener
```

## 2. Create a virtual environment
In the VS Code integrated terminal (`` Ctrl+` ``):
```
python -m venv venv
```
Activate it:
- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`

VS Code will usually prompt "Select Interpreter" — pick the one inside `venv`.

## 3. Install dependencies
```
pip install -r requirements-dev.txt
```
This installs the app's runtime dependencies plus `pytest` and `httpx` for testing.

## 4. Configure environment variables
```
cp .env.example .env
```
Then edit `.env` and set:
- `SECRET_KEY` — generate one with:
  ```
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — your dashboard login
- `BASE_URL` — leave as `http://127.0.0.1:8000` for local use

`.env` is in `.gitignore` and is never committed.

## 5. Run the app
```
uvicorn app.main:app --reload
```
- Dashboard: http://127.0.0.1:8000/dashboard
- API docs (Swagger): http://127.0.0.1:8000/docs
- API docs (ReDoc): http://127.0.0.1:8000/redoc

The SQLite database file is created automatically at `data/app.db` on first run.

## 6. Run the tests
```
pytest -v
```
Tests run against an isolated in-memory database, so they never touch `data/app.db`.

## Project layout
```
app/
  main.py            FastAPI app entrypoint, middleware, router wiring
  config.py          Settings loaded from .env
  database.py        SQLAlchemy engine/session
  models.py          ORM models (Link, Click)
  schemas.py         Pydantic request/response schemas
  crud.py            Database read/write operations
  analytics.py       Aggregate analytics queries
  routers/
    auth.py          Session login/logout
    dashboard.py     Server-rendered HTML dashboard
    links.py         JSON API for links
    redirect.py      Public /r/{code} redirect + click logging
  utils/
    shortcode.py     Short code generation/validation
    useragent.py     User-agent parsing
    geoip.py         Offline IP -> country lookup
  templates/         Jinja2 HTML templates
  static/            CSS
tests/                pytest suite
data/                 SQLite database file (gitignored)
docs/                 This guide + deployment guide
```

## Working with Gemini (or another AI) on this repo
Since the code is modular and each file has a single responsibility, you
can share individual files with another AI assistant without giving it
the whole repo. For example, to work on analytics with Gemini, share:
`app/analytics.py`, `app/models.py`, and the relevant template
(`app/templates/index.html` or `link_detail.html`). Mention this doc's
"Project layout" section so it understands where things fit.
