# Link Shortener

A self-hosted link shortener with UTM campaign builder and full click
backtrace logging (IP, geolocation, browser, OS, device type, referrer),
plus an analytics dashboard.

## Features
- Shorten any URL with auto-generated or custom short codes
- UTM campaign builder (source, medium, campaign, term, content) matching
  standard campaign-tracking parameters
- Every click logged: timestamp, IP, country (offline lookup, no API key
  needed), browser, OS, device type, referrer
- Dashboard with aggregate analytics: clicks over time, top referrers,
  device breakdown, top countries — both site-wide and per-link
- JSON API (with Swagger docs) alongside the HTML dashboard
- Session-based admin login
- SQLite by default, swappable to PostgreSQL via one config line

## Quick start
```
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env            # then edit SECRET_KEY / admin credentials
uvicorn app.main:app --reload
```
Visit http://127.0.0.1:8000/dashboard

Full instructions: [docs/SETUP.md](docs/SETUP.md)
Pushing to GitHub and deploying to a server: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Tech stack
- **Backend:** FastAPI + SQLAlchemy
- **Frontend:** Server-rendered Jinja2 templates (no build step)
- **Database:** SQLite (default), PostgreSQL-ready
- **Geolocation:** `geoip2fast` (offline, bundled database, no API key)
- **User-agent parsing:** `user-agents`
- **Tests:** pytest, 12 tests covering auth, link creation, redirects,
  click logging, and analytics aggregation

## Version history
| Tag | What it added |
|-----|----------------|
| v0.1 | Project scaffold, config, DB engine, ORM models |
| v0.2 | Auth, CRUD layer, dashboard UI, JSON API |
| v0.3 | Redirect endpoint with click logging, pytest suite |
| v0.4 | Aggregate analytics dashboard |

## License
Personal/internal use project — add a license here if you plan to share
or open-source it.
