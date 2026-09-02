"""
Database operations (CRUD), separated from route handlers so route
functions stay thin and this logic stays independently testable.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Link, Click
from app.utils.shortcode import generate_code, is_reserved
from app.utils.useragent import parse_user_agent
from app.utils.geoip import lookup_country
from app.config import settings


def code_exists(db: Session, code: str) -> bool:
    return db.query(Link).filter(Link.short_code == code).first() is not None


def make_unique_code(db: Session, length: int) -> str:
    """Generate a short code, retrying on the rare collision."""
    for _ in range(10):
        code = generate_code(length)
        if not code_exists(db, code) and not is_reserved(code):
            return code
    raise RuntimeError("Could not generate a unique short code, try again.")


def create_link(
    db: Session,
    long_url: str,
    utm_source: str,
    utm_medium: str,
    utm_campaign: str,
    utm_term: Optional[str] = None,
    utm_content: Optional[str] = None,
    custom_code: Optional[str] = None,
) -> Link:
    if custom_code:
        if is_reserved(custom_code):
            raise ValueError(f"'{custom_code}' is a reserved word, pick another code.")
        if code_exists(db, custom_code):
            raise ValueError(f"Short code '{custom_code}' is already taken.")
        code = custom_code
    else:
        code = make_unique_code(db, settings.shortcode_length)

    link = Link(
        short_code=code,
        long_url=str(long_url),
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_term=utm_term or None,
        utm_content=utm_content or None,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_link_by_code(db: Session, code: str) -> Optional[Link]:
    return db.query(Link).filter(Link.short_code == code).first()


def get_link_by_id(db: Session, link_id: int) -> Optional[Link]:
    return db.query(Link).filter(Link.id == link_id).first()


def list_links(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(Link)
        .order_by(Link.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_clicks(db: Session, link_id: int) -> int:
    return db.query(func.count(Click.id)).filter(Click.link_id == link_id).scalar() or 0


def deactivate_link(db: Session, link_id: int) -> Optional[Link]:
    link = get_link_by_id(db, link_id)
    if link:
        link.is_active = False
        db.commit()
        db.refresh(link)
    return link


def log_click(
    db: Session,
    link_id: int,
    ip_address: Optional[str],
    referrer: Optional[str],
    user_agent_raw: Optional[str],
) -> Click:
    """Record one redirect hit with full backtrace data (called from the
    redirect route before it sends the 302)."""
    ua_info = parse_user_agent(user_agent_raw or "")
    geo_info = lookup_country(ip_address or "")

    click = Click(
        link_id=link_id,
        ip_address=ip_address,
        referrer=referrer,
        user_agent_raw=user_agent_raw,
        browser=ua_info["browser"],
        os=ua_info["os"],
        device_type=ua_info["device_type"],
        country=geo_info["country"],
        city=geo_info["city"],
    )
    db.add(click)
    db.commit()
    db.refresh(click)
    return click


def delete_link(db: Session, link_id: int) -> bool:
    link = get_link_by_id(db, link_id)
    if not link:
        return False
    db.delete(link)
    db.commit()
    return True
