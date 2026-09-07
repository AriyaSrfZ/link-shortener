# Link Shortener

A self-hosted link shortener with UTM campaign builder and full click
backtrace logging (IP, geolocation, browser, OS, device type, referrer),
plus an analytics dashboard.

Built by Ariya Sarrafzadeh ([github.com/AriyaSrfZ](https://github.com/AriyaSrfZ)).

## Features
- Shorten any URL with auto-generated or custom short codes
- UTM campaign builder (source, medium, campaign, term, content) matching
  standard campaign-tracking parameters
- Every click logged: timestamp, IP, country (offline lookup, no API key
  needed), browser, OS, device type, referrer
- **Multi-tenant**: customers self-register and only ever see their own
  links; an admin account sees and manages everything, plus a Customers
  page to disable or delete accounts
- Dashboard with live Chart.js graphs (line, doughnut, bar) — site-wide
  for admins, scoped to just their own links for customers
- X-API-Key auth for external app integration, plus admin/API-key account
  provisioning (`POST /api/users`) for panels/apps that need to create
  accounts automatically
- QR codes: for any short link (dynamic — edit the link, the code updates,
  no reprint) or standalone (text, WiFi, contact card), PNG + SVG
- Click-free link preview page (`/preview/{code}`) — see the destination
  without triggering a tracked visit
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
API reference for integrating into another app: [docs/API.md](docs/API.md)
Uploading this repo to GitHub: [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md)
Running it on WSL with a real domain (Cloudflare Tunnel): [docs/WSL_CLOUDFLARE_SETUP.md](docs/WSL_CLOUDFLARE_SETUP.md)
Deploying to a VPS with a domain: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

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
| v0.11 | X-API-Key auth for app integration, click/stats API endpoints, full OpenAPI docs |
| v0.12 | Multi-tenant: database-backed users, customer signup, ownership enforcement, admin user management |
| v0.13 | Redesigned dashboard with real Chart.js graphs |
| v0.15 | QR codes (link/text/wifi/vcard), click-free link preview, API account provisioning |

See [docs/ARCHITECTURE_USER_MANAGEMENT.md](docs/ARCHITECTURE_USER_MANAGEMENT.md)
for the plan to extract user accounts into a shared service once a
second project needs them.

## License
Personal/internal use project — add a license here if you plan to share
or open-source it.

## Author
Ariya Sarrafzadeh — [github.com/AriyaSrfZ](https://github.com/AriyaSrfZ)
