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

from app.main import app  # noqa: E402
from app.database import Base, engine, get_db, SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.routers.auth import hash_password  # noqa: E402

# Use a single shared in-memory connection for the whole test session,
# since SQLite ":memory:" is per-connection otherwise.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # single shared connection, so :memory: persists across sessions
)
TestSessionLocal = sessionmaker(bind=test_engine)
Base.metadata.create_all(bind=test_engine)

# Bootstrap an admin user directly, same as scripts/migrate_multi_tenant.py
# does for a real install - login now checks the users table, not .env.
with TestSessionLocal() as _db:
    if not _db.query(User).filter(User.role == "admin").first():
        _db.add(User(
            username="admin",
            password_hash=hash_password("testpass"),
            role="admin",
            is_active=True,
        ))
        _db.commit()


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _use_test_db():
    """Applies this file's DB override only while this file's tests run,
    then restores whatever was there before. Without this, whichever test
    file pytest imports last would silently win for every test in the
    whole run, since dependency_overrides is a single shared dict on the
    one `app` object all test files import."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous
    else:
        app.dependency_overrides.pop(get_db, None)


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


def test_login_rate_limited_after_too_many_attempts():
    """Isolated app instance with a very low limit, so it doesn't
    interfere with the shared high-limit fixture used everywhere else
    in this file."""
    import os as _os
    _os.environ["RATE_LIMIT_LOGIN"] = "3/minute"
    import importlib
    import app.config as config_module
    importlib.reload(config_module)
    import app.routers.auth as auth_module
    importlib.reload(auth_module)

    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware

    isolated_app = FastAPI()
    isolated_app.state.limiter = auth_module.limiter
    isolated_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    isolated_app.add_middleware(SessionMiddleware, secret_key="test")
    isolated_app.include_router(auth_module.router)
    isolated_app.dependency_overrides[get_db] = override_get_db

    with TestClient(isolated_app) as ic:
        statuses = [ic.post("/login", data={"username": "nobody", "password": "wrong"}).status_code for _ in range(5)]
    assert 429 in statuses

    _os.environ["RATE_LIMIT_LOGIN"] = "1000/minute"
    importlib.reload(config_module)
    importlib.reload(auth_module)


def test_create_link_custom_code_invalid_chars(logged_in_client):
    # Slashes, spaces, emojis, or punctuation should be rejected
    for bad_code in ["slash/code", "space code", "emoji🚀", "question?mark", "hash#tag"]:
        r = logged_in_client.post(
            "/api/links",
            json={
                "long_url": "https://example.com",
                "utm_source": "test",
                "utm_medium": "test",
                "utm_campaign": "test",
                "custom_code": bad_code,
            },
        )
        assert r.status_code in (400, 422), f"Expected rejection for '{bad_code}', got {r.status_code}"


def test_link_clicks_pagination(logged_in_client, client):
    create_resp = logged_in_client.post(
        "/api/links",
        json={
            "long_url": "https://example.com/target",
            "utm_source": "src",
            "utm_medium": "med",
            "utm_campaign": "cmp",
        },
    )
    assert create_resp.status_code == 200
    link_id = create_resp.json()["id"]
    short_code = create_resp.json()["short_code"]

    # Simulate 5 clicks via anonymous client
    for _ in range(5):
        client.get(f"/r/{short_code}", follow_redirects=False)

    # Query clicks with pagination
    r_all = logged_in_client.get(f"/api/links/{link_id}/clicks?skip=0&limit=10")
    assert len(r_all.json()) == 5

    r_page1 = logged_in_client.get(f"/api/links/{link_id}/clicks?skip=0&limit=2")
    assert len(r_page1.json()) == 2

    r_page2 = logged_in_client.get(f"/api/links/{link_id}/clicks?skip=2&limit=2")
    assert len(r_page2.json()) == 2
    assert r_page1.json()[0]["id"] != r_page2.json()[0]["id"]


def test_redirect_records_cf_connecting_ip(logged_in_client, client):
    create_resp = logged_in_client.post(
        "/api/links",
        json={
            "long_url": "https://example.com/target",
            "utm_source": "src",
            "utm_medium": "med",
            "utm_campaign": "cmp",
        },
    )
    link_id = create_resp.json()["id"]
    short_code = create_resp.json()["short_code"]

    # Click with CF-Connecting-IP header via anonymous client
    client.get(f"/r/{short_code}", headers={"cf-connecting-ip": "198.51.100.42"}, follow_redirects=False)

    clicks_resp = logged_in_client.get(f"/api/links/{link_id}/clicks?limit=1")
    clicks = clicks_resp.json()
    assert len(clicks) >= 1
    assert clicks[0]["ip_address"] == "198.51.100.42"

