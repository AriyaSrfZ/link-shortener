# Link Shortener

A lightweight, self-hosted URL shortener with UTM campaign tracking, offline click geolocation, device telemetry analytics, and multi-tenant account isolation.

## Features

- **URL Shortening**: Generate custom or random base62 short codes with fast 302/307 redirects.
- **UTM Campaign Builder**: Attach standardized campaign attribution tags (`utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`).
- **Telemetry & Logging**: Log timestamp, IP, country (via offline GeoIP database, no external API needed), browser, operating system, and referrer for every click.
- **Multi-Tenant Access Control**: Scoped customer registration where users manage their own links, paired with an administrative console.
- **Analytics Dashboard**: Interactive Chart.js visual charts for click volume trends, top referrers, geographic breakdown, and device types.
- **API & Account Provisioning**: `X-API-Key` authentication for automated integration and programmatic link creation.
- **Click-Free Preview**: Safe `/preview/{code}` route to inspect destination URLs without triggering a tracked click.
- **Database Flexibility**: Runs on SQLite out of the box, with one-line configuration for PostgreSQL.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/dashboard` in your browser.

## API Documentation

Interactive API documentation and schema specifications are served locally at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Tech Stack

- **Framework**: FastAPI (Python 3.13)
- **Database & ORM**: SQLAlchemy (SQLite / PostgreSQL)
- **Templates**: Jinja2 + Chart.js
- **Geolocation**: `geoip2fast` (offline embedded MaxMind database)
- **User-Agent Parsing**: `user-agents`
- **Testing**: `pytest` comprehensive test suite

## Testing

Run the test suite with:

```bash
pytest tests/
```
