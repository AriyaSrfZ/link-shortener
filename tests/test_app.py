"""
End-to-end tests against the real FastAPI app, using an isolated in-memory
SQLite database so tests never touch data/app.db.

Run with: pytest
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Point at an in-memory DB before importing the app, so app.database picks
# it up via the same engine-creation path as production.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass"

from app.main import app  # noqa: E402
from app.database import Base, engine, get_db, SessionLocal  # noqa: E402

# Use a single shared in-memory connection for the whole test session,
# since SQLite ":memory:" is per-connection otherwise.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # single shared connection, so :memory: persists across sessions
)
TestSessionLocal = sessionmaker(bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def logged_in_client(client):
    client.post("/login", data={"username": "admin", "password": "testpass"})
    return client


def test_dashboard_requires_login(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_wrong_password(client):
    r = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_success(client):
    r = client.post(
        "/login", data={"username": "admin", "password": "testpass"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


def test_create_link_and_redirect_logs_click(logged_in_client):
    r = logged_in_client.post(
        "/dashboard/new",
        data={
            "long_url": "https://example.com/product",
            "utm_source": "newsletter",
            "utm_medium": "sms",
            "utm_campaign": "launch",
            "utm_term": "",
            "utm_content": "",
            "custom_code": "testcode1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    detail_url = r.headers["location"]

    # Hit the public redirect as an anonymous visitor (no auth needed)
    r = logged_in_client.get(
        "/r/testcode1",
        headers={
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0"
            ),
            "referer": "https://google.com",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "utm_source=newsletter" in r.headers["location"]
    assert "utm_medium=sms" in r.headers["location"]
    assert "utm_campaign=launch" in r.headers["location"]

    # Detail page shows the click
    r = logged_in_client.get(detail_url)
    assert r.status_code == 200
    assert "testcode1" in r.text
    assert "Chrome" in r.text


def test_duplicate_custom_code_rejected(logged_in_client):
    payload = {
        "long_url": "https://example.com/a",
        "utm_source": "a",
        "utm_medium": "a",
        "utm_campaign": "a",
        "utm_term": "",
        "utm_content": "",
        "custom_code": "dupe1",
    }
    r1 = logged_in_client.post("/dashboard/new", data=payload, follow_redirects=False)
    assert r1.status_code == 303

    r2 = logged_in_client.post("/dashboard/new", data=payload, follow_redirects=False)
    assert r2.status_code == 400
    assert "already taken" in r2.text


def test_inactive_or_unknown_code_redirects_to_dashboard(logged_in_client):
    r = logged_in_client.get("/r/doesnotexist", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


def test_json_api_requires_auth(client):
    r = client.get("/api/links")
    assert r.status_code == 401
