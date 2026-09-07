"""
Database operations (CRUD), separated from route handlers so route
functions stay thin and this logic stays independently testable.

Ownership model: every Link belongs to exactly one User (owner_id).
Functions suffixed `_for_user` enforce that a customer only ever sees
their own links - they return None/empty for anything they don't own,
the same as if it didn't exist (never a 403, which would confirm the
link's existence to someone probing IDs). Admins and API-key requests
bypass this filtering entirely (see CurrentUser.is_admin).
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Link, Click, User, QRCode
from app.utils.shortcode import generate_code, is_reserved
from app.utils.useragent import parse_user_agent
from app.utils.geoip import lookup_country
from app.config import settings


# ---- Links -----------------------------------------------------------

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
    owner_id: Optional[int] = None,
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
        owner_id=owner_id,
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


def get_link_for_user(db: Session, link_id: int, current_user) -> Optional[Link]:
    """Ownership-checked lookup. Returns None if the link doesn't exist
    OR belongs to someone else - callers should treat both as 404."""
    link = get_link_by_id(db, link_id)
    if not link:
        return None
    if current_user.is_admin or link.owner_id == current_user.id:
        return link
    return None


def list_links(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(Link)
        .order_by(Link.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_links_for_user(db: Session, current_user, skip: int = 0, limit: int = 100):
    """Admin/API-key: all links. Customer: only their own."""
    query = db.query(Link)
    if not current_user.is_admin:
        query = query.filter(Link.owner_id == current_user.id)
    return query.order_by(Link.created_at.desc()).offset(skip).limit(limit).all()


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


def delete_link_for_user(db: Session, link_id: int, current_user) -> bool:
    link = get_link_for_user(db, link_id, current_user)
    if not link:
        return False
    db.delete(link)
    db.commit()
    return True


# ---- Users (admin's customer-management panel) ------------------------

def create_user(db: Session, username: str, password_hash: str, email: Optional[str] = None, role: str = "customer") -> User:
    user = User(username=username, email=email, password_hash=password_hash, role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def username_taken(db: Session, username: str) -> bool:
    return db.query(User).filter(User.username == username).first() is not None


def email_taken(db: Session, email: str) -> bool:
    return db.query(User).filter(User.email == email).first() is not None


def list_customers(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(User)
        .filter(User.role == "customer")
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def count_links_for_owner(db: Session, owner_id: int) -> int:
    return db.query(func.count(Link.id)).filter(Link.owner_id == owner_id).scalar() or 0


def set_user_active(db: Session, user_id: int, is_active: bool) -> Optional[User]:
    user = get_user_by_id(db, user_id)
    if user and user.role != "admin":
        user.is_active = is_active
        db.commit()
        db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """Deletes a customer and all their links (cascade). Refuses to delete admins."""
    user = get_user_by_id(db, user_id)
    if not user or user.role == "admin":
        return False
    db.delete(user)
    db.commit()
    return True


# ---- QR codes -----------------------------------------------------------

def create_qr_code(
    db: Session,
    owner_id: int,
    qr_type: str,
    link_id: Optional[int] = None,
    payload: Optional[str] = None,
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
) -> QRCode:
    qr = QRCode(
        owner_id=owner_id,
        type=qr_type,
        link_id=link_id,
        payload=payload,
        fg_color=fg_color,
        bg_color=bg_color,
    )
    db.add(qr)
    db.commit()
    db.refresh(qr)
    return qr


def get_qr_code_by_id(db: Session, qr_id: int) -> Optional[QRCode]:
    return db.query(QRCode).filter(QRCode.id == qr_id).first()


def get_qr_code_for_user(db: Session, qr_id: int, current_user) -> Optional[QRCode]:
    qr = get_qr_code_by_id(db, qr_id)
    if not qr:
        return None
    if current_user.is_admin or qr.owner_id == current_user.id:
        return qr
    return None


def list_qr_codes_for_user(db: Session, current_user, skip: int = 0, limit: int = 100):
    query = db.query(QRCode)
    if not current_user.is_admin:
        query = query.filter(QRCode.owner_id == current_user.id)
    return query.order_by(QRCode.created_at.desc()).offset(skip).limit(limit).all()


def delete_qr_code_for_user(db: Session, qr_id: int, current_user) -> bool:
    qr = get_qr_code_for_user(db, qr_id, current_user)
    if not qr:
        return False
    db.delete(qr)
    db.commit()
    return True
