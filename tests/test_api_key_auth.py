"""
Tests for API key authentication and the click log / stats endpoints
added for external app integration. Uses the same in-memory DB pattern
as test_app.py.
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
from app.database import Base, get_db  # noqa: E402

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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

API_KEY_HEADER = {"X-API-Key": "test-api-key-123"}


@pytest.fixture()
def client():
    return TestClient(app)


def test_api_rejects_missing_key(client):
    r = client.get("/api/links")
    assert r.status_code == 401


def test_api_rejects_wrong_key(client):
    r = client.get("/api/links", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_api_accepts_correct_key_no_cookies_needed(client):
    r = client.post(
        "/api/links",
        json={
            "long_url": "https://example.com/product",
            "utm_source": "app",
            "utm_medium": "api",
            "utm_campaign": "test",
            "custom_code": "keytest1",
        },
        headers=API_KEY_HEADER,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["short_code"] == "keytest1"
    assert body["final_url"].endswith(
        "?utm_source=app&utm_medium=api&utm_campaign=test"
    )


def test_clicks_and_stats_endpoints(client):
    r = client.post(
        "/api/links",
        json={
            "long_url": "https://example.com/x",
            "utm_source": "app",
            "utm_medium": "api",
            "utm_campaign": "test2",
            "custom_code": "keytest2",
        },
        headers=API_KEY_HEADER,
    )
    link_id = r.json()["id"]

    client.get(
        "/r/keytest2",
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"},
        follow_redirects=False,
    )

    r = client.get(f"/api/links/{link_id}/clicks", headers=API_KEY_HEADER)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["browser"].startswith("Chrome")

    r = client.get(f"/api/links/{link_id}/stats", headers=API_KEY_HEADER)
    assert r.status_code == 200
    assert r.json()["summary"]["total"] == 1

    r = client.get("/api/stats", headers=API_KEY_HEADER)
    assert r.status_code == 200
    assert r.json()["summary"]["total"] >= 1


def test_clicks_endpoint_404_for_unknown_link(client):
    r = client.get("/api/links/999999/clicks", headers=API_KEY_HEADER)
    assert r.status_code == 404
