"""
Tests for the preview page and API-driven account provisioning.
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
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestSessionLocal = sessionmaker(bind=test_engine)
Base.metadata.create_all(bind=test_engine)

with TestSessionLocal() as _db:
    if not _db.query(User).filter(User.username == "admin_prov").first():
        _db.add(User(username="admin_prov", password_hash=hash_password("adminpass"), role="admin", is_active=True))
        _db.commit()


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _use_test_db():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous
    else:
        app.dependency_overrides.pop(get_db, None)


API_KEY = {"X-API-Key": "test-api-key-123"}


@pytest.fixture()
def client():
    return TestClient(app)


def make_link(client, code):
    client.post("/login", data={"username": "admin_prov", "password": "adminpass"})
    r = client.post(
        "/dashboard/new",
        data={"long_url": "https://example.com/p", "utm_source": "a", "utm_medium": "a",
              "utm_campaign": "a", "utm_term": "", "utm_content": "", "custom_code": code},
        follow_redirects=False,
    )
    link_id = int(r.headers["location"].rstrip("/").split("/")[-1])
    client.get("/logout")
    return link_id


# ---- Preview -----------------------------------------------------------

def test_preview_shows_destination_without_logging_click(client):
    link_id = make_link(client, "prevtest1")
    r = client.get("/preview/prevtest1")
    assert r.status_code == 200
    assert "example.com/p" in r.text

    r2 = client.get(f"/api/links/{link_id}/clicks", headers=API_KEY)
    assert r2.json() == []


def test_preview_unknown_code(client):
    r = client.get("/preview/doesnotexist")
    assert r.status_code == 200
    assert "No link found" in r.text


# ---- Account provisioning ------------------------------------------------

def test_provision_user_via_api_key_generates_password(client):
    r = client.post("/api/users", json={"username": "provisioned1"}, headers=API_KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "customer"
    assert body["generated_password"]

    r2 = client.post("/login", data={"username": "provisioned1", "password": body["generated_password"]}, follow_redirects=False)
    assert r2.status_code == 303


def test_provision_user_with_explicit_password(client):
    r = client.post("/api/users", json={"username": "provisioned2", "password": "myownpassword1"}, headers=API_KEY)
    assert r.status_code == 200
    assert r.json()["generated_password"] is None


def test_provision_duplicate_username_rejected(client):
    client.post("/api/users", json={"username": "duptest1"}, headers=API_KEY)
    r = client.post("/api/users", json={"username": "duptest1"}, headers=API_KEY)
    assert r.status_code == 400


def test_customer_cannot_provision_users(client):
    client.post("/signup", data={"username": "notadmin1", "email": "", "password": "password123", "password_confirm": "password123"})
    r = client.post("/api/users", json={"username": "sneaky1"})
    assert r.status_code == 403


def test_provisioning_requires_auth_at_all(client):
    r = client.post("/api/users", json={"username": "noauth1"})
    assert r.status_code == 401
