"""
Focused tests for app/analytics.py aggregation queries, using the same
in-memory DB pattern as test_app.py but calling the functions directly
rather than through the HTTP layer.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base  # noqa: E402
from app.models import Link, Click  # noqa: E402
from app import analytics  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    link = Link(
        short_code="abc123",
        long_url="https://example.com",
        utm_source="s", utm_medium="m", utm_campaign="c",
    )
    session.add(link)
    session.commit()
    session.refresh(link)

    clicks = [
        Click(link_id=link.id, referrer="https://google.com", device_type="desktop", country="Germany"),
        Click(link_id=link.id, referrer="https://google.com", device_type="mobile", country="Germany"),
        Click(link_id=link.id, referrer=None, device_type="mobile", country="Iran"),
    ]
    session.add_all(clicks)
    session.commit()

    yield session, link.id
    session.close()


def test_top_referrers(db_session):
    session, link_id = db_session
    result = analytics.top_referrers(session, link_id=link_id)
    assert result[0]["referrer"] == "https://google.com"
    assert result[0]["count"] == 2


def test_device_breakdown(db_session):
    session, link_id = db_session
    result = analytics.device_breakdown(session, link_id=link_id)
    counts = {r["device_type"]: r["count"] for r in result}
    assert counts["mobile"] == 2
    assert counts["desktop"] == 1


def test_top_countries(db_session):
    session, link_id = db_session
    result = analytics.top_countries(session, link_id=link_id)
    counts = {r["country"]: r["count"] for r in result}
    assert counts["Germany"] == 2
    assert counts["Iran"] == 1


def test_total_clicks_summary(db_session):
    session, link_id = db_session
    result = analytics.total_clicks_summary(session, link_id=link_id)
    assert result["total"] == 3


def test_clicks_per_day_includes_zero_days(db_session):
    session, link_id = db_session
    result = analytics.clicks_per_day(session, link_id=link_id, days=7)
    assert len(result) == 7
    today = datetime.now(timezone.utc).date().isoformat()
    today_row = next(r for r in result if r["day"] == today)
    assert today_row["count"] == 3
