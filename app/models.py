"""
ORM models.

Link:  one row per shortened URL, holds the destination and UTM parameters.
Click: one row per redirect hit against a Link, holds the backtrace data.
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(64), unique=True, index=True, nullable=False)
    long_url = Column(Text, nullable=False)

    # UTM parameters - required fields per the campaign builder
    utm_source = Column(String(255), nullable=False)
    utm_medium = Column(String(255), nullable=False)
    utm_campaign = Column(String(255), nullable=False)

    # UTM parameters - optional fields
    utm_term = Column(String(255), nullable=True)
    utm_content = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    clicks = relationship(
        "Click", back_populates="link", cascade="all, delete-orphan"
    )

    @property
    def final_url(self) -> str:
        """The long URL with UTM query parameters appended."""
        from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

        params = {
            "utm_source": self.utm_source,
            "utm_medium": self.utm_medium,
            "utm_campaign": self.utm_campaign,
        }
        if self.utm_term:
            params["utm_term"] = self.utm_term
        if self.utm_content:
            params["utm_content"] = self.utm_content

        parsed = urlparse(self.long_url)
        existing = dict(parse_qsl(parsed.query))
        existing.update(params)
        new_query = urlencode(existing)
        return urlunparse(parsed._replace(query=new_query))


class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.id"), nullable=False)

    clicked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    referrer = Column(Text, nullable=True)
    user_agent_raw = Column(Text, nullable=True)

    # Parsed user-agent breakdown
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile / tablet / desktop / bot

    # Geo breakdown (from offline IP database, best-effort)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)

    link = relationship("Link", back_populates="clicks")
