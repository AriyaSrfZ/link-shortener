"""
Tests for the multi-tenant model: signup, per-customer ownership
enforcement, and admin-only user management. The isolation tests here
are the important ones - a customer must never be able to read,
enumerate, or delete another customer's links, via the dashboard OR
the JSON API.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models import User  # noqa: E402
from app.routers.auth import hash_password  # noqa: E402

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine)
Base.metadata.create_all(bind=test_engine)

with TestSessionLocal() as _db:
    if not _db.query(User).filter(User.role == "admin").first():
        _db.add(User(
            username="admin_mt",
            password_hash=hash_password("adminpass"),
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


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _use_test_db():
    """See test_app.py for why this fixture (not a bare module-level
    assignment) is required for correct test isolation."""
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


def signup(client, username, password="password123"):
    return client.post(
        "/signup",
        data={"username": username, "email": "", "password": password, "password_confirm": password},
        follow_redirects=False,
    )


def test_signup_creates_customer_and_logs_in(client):
    r = signup(client, "alice1")
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"

    r = client.get("/dashboard")
    assert r.status_code == 200
    # Customers don't get the "Customers" admin link in the nav
    assert "Customers</a>" not in r.text


def test_signup_rejects_duplicate_username(client):
    signup(client, "bob1")
    r = signup(client, "bob1")
    assert r.status_code == 400
    assert "already taken" in r.text


def test_signup_rejects_short_password(client):
    r = client.post(
        "/signup",
        data={"username": "shortpw1", "email": "", "password": "abc", "password_confirm": "abc"},
    )
    assert r.status_code == 400
    assert "at least 8 characters" in r.text


def test_customer_cannot_see_another_customers_link(client):
    # Customer A creates a link
    signup(client, "custa1")
    r = client.post(
        "/dashboard/new",
        data={
            "long_url": "https://example.com/a",
            "utm_source": "a", "utm_medium": "a", "utm_campaign": "a",
            "utm_term": "", "utm_content": "", "custom_code": "isoa1",
        },
        follow_redirects=False,
    )
    link_url = r.headers["location"]
    link_id = link_url.rstrip("/").split("/")[-1]
    client.get("/logout")

    # Customer B logs in and tries to view A's link directly by ID
    signup(client, "custb1")
    r = client.get(f"/dashboard/{link_id}", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"  # bounced, not shown

    # B's own link list is empty (doesn't include A's link)
    r = client.get("/dashboard")
    assert "isoa1" not in r.text


def test_customer_cannot_access_another_customers_link_via_api(client):
    signup(client, "custc1")
    r = client.post(
        "/dashboard/new",
        data={
            "long_url": "https://example.com/c",
            "utm_source": "c", "utm_medium": "c", "utm_campaign": "c",
            "utm_term": "", "utm_content": "", "custom_code": "isoc1",
        },
        follow_redirects=False,
    )
    link_id = r.headers["location"].rstrip("/").split("/")[-1]
    client.get("/logout")

    signup(client, "custd1")
    # Same browser session (customer D), hitting the JSON API directly
    r = client.get(f"/api/links/{link_id}")
    assert r.status_code == 404  # not 403 - existence isn't confirmed either

    r = client.get(f"/api/links/{link_id}/clicks")
    assert r.status_code == 404

    r = client.delete(f"/api/links/{link_id}")
    assert r.status_code == 404

    # D's own /api/links list doesn't include C's link
    r = client.get("/api/links")
    codes = [l["short_code"] for l in r.json()]
    assert "isoc1" not in codes


def test_admin_sees_all_links_customer_only_sees_own(client):
    signup(client, "custe1")
    client.post(
        "/dashboard/new",
        data={
            "long_url": "https://example.com/e",
            "utm_source": "e", "utm_medium": "e", "utm_campaign": "e",
            "utm_term": "", "utm_content": "", "custom_code": "isoe1",
        },
    )
    r = client.get("/api/links")
    codes = [l["short_code"] for l in r.json()]
    assert codes == ["isoe1"]
    client.get("/logout")

    client.post("/login", data={"username": "admin_mt", "password": "adminpass"})
    r = client.get("/api/links")
    codes = [l["short_code"] for l in r.json()]
    assert "isoe1" in codes  # admin sees it too


def test_customer_cannot_access_admin_user_management(client):
    signup(client, "custf1")
    r = client.get("/dashboard/admin/users")
    assert r.status_code == 403


def test_admin_can_manage_customers(client):
    signup(client, "custg1")
    client.get("/logout")

    client.post("/login", data={"username": "admin_mt", "password": "adminpass"})
    r = client.get("/dashboard/admin/users")
    assert r.status_code == 200
    assert "custg1" in r.text

    # Find the customer's id via the users API path isn't exposed, so
    # toggle by scanning - simplest is to check the page renders the
    # disable button, which confirms the route and template work end to end.
    assert "Disable" in r.text
