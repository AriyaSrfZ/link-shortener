"""
Pydantic schemas: define the shape of API input/output, separate from
the ORM models in models.py. Keeps the DB layer and the API contract
independent, so one can change without breaking the other.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field


class LinkCreate(BaseModel):
    long_url: HttpUrl
    utm_source: str = Field(..., min_length=1, max_length=255)
    utm_medium: str = Field(..., min_length=1, max_length=255)
    utm_campaign: str = Field(..., min_length=1, max_length=255)
    utm_term: Optional[str] = Field(None, max_length=255)
    utm_content: Optional[str] = Field(None, max_length=255)
    custom_code: Optional[str] = Field(
        None, min_length=3, max_length=64,
        description="Leave blank to auto-generate a short code."
    )


class LinkOut(BaseModel):
    id: int
    short_code: str
    short_url: str
    long_url: str
    final_url: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    is_active: bool
    created_at: datetime
    click_count: int = 0

model_config = {"from_attributes": True}


class ClickOut(BaseModel):
    id: int
    clicked_at: datetime
    ip_address: Optional[str] = None
    referrer: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None

model_config = {"from_attributes": True}
