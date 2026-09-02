"""
Aggregate analytics queries, kept separate from crud.py since these are
read-only rollups for the dashboard rather than record-level CRUD.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Click


def clicks_per_day(db: Session, link_id: Optional[int] = None, days: int = 14) -> list[dict]:
    """Click counts for the last N days, oldest first. Days with zero
    clicks are included so the chart doesn't have gaps."""
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    query = db.query(
        func.date(Click.clicked_at).label("day"),
        func.count(Click.id).label("count"),
    ).filter(Click.clicked_at >= since)

    if link_id is not None:
        query = query.filter(Click.link_id == link_id)

    rows = {r.day: r.count for r in query.group_by("day").all()}

    result = []
    for i in range(days):
        day = (since + timedelta(days=i)).date()
        key = day.isoformat()
        result.append({"day": key, "count": rows.get(key, 0)})
    return result


def top_referrers(db: Session, link_id: Optional[int] = None, limit: int = 5) -> list[dict]:
    query = db.query(
        Click.referrer,
        func.count(Click.id).label("count"),
    )
    if link_id is not None:
        query = query.filter(Click.link_id == link_id)

    rows = (
        query.group_by(Click.referrer)
        .order_by(func.count(Click.id).desc())
        .limit(limit)
        .all()
    )
    return [{"referrer": r.referrer or "Direct / unknown", "count": r.count} for r in rows]


def device_breakdown(db: Session, link_id: Optional[int] = None) -> list[dict]:
    query = db.query(
        Click.device_type,
        func.count(Click.id).label("count"),
    )
    if link_id is not None:
        query = query.filter(Click.link_id == link_id)

    rows = (
        query.group_by(Click.device_type)
        .order_by(func.count(Click.id).desc())
        .all()
    )
    return [{"device_type": r.device_type or "unknown", "count": r.count} for r in rows]


def top_countries(db: Session, link_id: Optional[int] = None, limit: int = 5) -> list[dict]:
    query = db.query(
        Click.country,
        func.count(Click.id).label("count"),
    )
    if link_id is not None:
        query = query.filter(Click.link_id == link_id)

    rows = (
        query.group_by(Click.country)
        .order_by(func.count(Click.id).desc())
        .limit(limit)
        .all()
    )
    return [{"country": r.country or "Unknown", "count": r.count} for r in rows]


def total_clicks_summary(db: Session, link_id: Optional[int] = None) -> dict:
    query = db.query(func.count(Click.id))
    if link_id is not None:
        query = query.filter(Click.link_id == link_id)
    total = query.scalar() or 0

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    q24 = db.query(func.count(Click.id)).filter(Click.clicked_at >= since_24h)
    if link_id is not None:
        q24 = q24.filter(Click.link_id == link_id)
    last_24h = q24.scalar() or 0

    return {"total": total, "last_24h": last_24h}
