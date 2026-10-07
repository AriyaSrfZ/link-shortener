"""
Pydantic schemas: define the shape of API input/output, separate from
the ORM models in models.py. Keeps the DB layer and the API contract
independent, so one can change without breaking the other.

Every field carries a `description` and `examples` value so the
auto-generated docs at /docs and /redoc are a complete reference for
anyone integrating against this API without reading the source code.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field


class LinkCreate(BaseModel):
    long_url: HttpUrl = Field(
        ...,
        description="The destination URL to shorten. Must include the scheme (http:// or https://).",
        examples=["https://example.com/product?id=42"],
    )
    utm_source: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Required. Identifies the traffic source, e.g. the platform or channel sending the click.",
        examples=["newsletter", "instagram", "sms_campaign"],
    )
    utm_medium: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Required. Identifies the marketing medium, e.g. how the link was delivered.",
        examples=["email", "sms", "cpc", "social"],
    )
    utm_campaign: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Required. Identifies the specific campaign or promotion this link belongs to.",
        examples=["summer_sale_2026", "product_launch"],
    )
    utm_term: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional. Identifies paid search keywords, if applicable. Omit or leave blank if not used.",
        examples=["running_shoes"],
    )
    utm_content: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional. Differentiates similar content or links within the same ad/campaign, e.g. an A/B test variant.",
        examples=["banner_a", "text_link"],
    )
    custom_code: Optional[str] = Field(
        None,
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description=(
            "Optional. Letters, digits, underscore, and hyphen only. "
            "Leave blank/omit to auto-generate a random 6-character code. "
            "Fails with 400 if the code is already taken or reserved."
        ),
        examples=["summer2026"],
    )


class LinkOut(BaseModel):
    id: int = Field(..., description="Internal numeric ID of the link.")
    short_code: str = Field(..., description="The short code portion (what follows /r/ in the short URL).")
    short_url: str = Field(..., description="The full short URL to distribute, e.g. https://aria-haross.ir/r/abc123.")
    long_url: str = Field(..., description="The original destination URL, without UTM parameters appended.")
    final_url: str = Field(..., description="The long_url with all UTM parameters appended. This is where /r/{code} actually redirects to.")
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    is_active: bool = Field(..., description="If false, the redirect endpoint stops resolving this link (soft-disable).")
    created_at: datetime
    click_count: int = Field(0, description="Total number of recorded clicks for this link.")

    model_config = {"from_attributes": True}


class ClickOut(BaseModel):
    id: int
    clicked_at: datetime = Field(..., description="UTC timestamp of the click.")
    ip_address: Optional[str] = Field(None, description="Visitor's IP address (or the first entry in X-Forwarded-For if behind a proxy).")
    referrer: Optional[str] = Field(None, description="The Referer header sent by the visitor's browser, if any. Null if the click was direct.")
    browser: Optional[str] = Field(None, description="Parsed browser name and version, e.g. 'Chrome 120.0'.")
    os: Optional[str] = Field(None, description="Parsed operating system name and version, e.g. 'iOS 17.0'.")
    device_type: Optional[str] = Field(None, description="One of: desktop, mobile, tablet, bot, unknown.")
    country: Optional[str] = Field(None, description="Country resolved from the visitor's IP (offline lookup). Null for private/local IPs or unresolvable addresses.")
    city: Optional[str] = None

    model_config = {"from_attributes": True}


class QRCodeCreate(BaseModel):
    type: str = Field(..., description="One of: link, text, wifi, vcard.", examples=["link"])
    link_id: Optional[int] = Field(None, description="Required when type='link'. The ID of one of your existing links.")
    text: Optional[str] = Field(None, description="Required when type='text'. The raw text to encode.")
    wifi_ssid: Optional[str] = Field(None, description="Required when type='wifi'. The network name.")
    wifi_password: Optional[str] = Field(None, description="Used when type='wifi' and wifi_security is not 'nopass'.")
    wifi_security: Optional[str] = Field("WPA", description="Used when type='wifi'. One of: WPA, WEP, nopass.")
    wifi_hidden: Optional[bool] = Field(False, description="Used when type='wifi'. Whether the network is hidden.")
    vcard_name: Optional[str] = Field(None, description="Required when type='vcard'. Contact's full name.")
    vcard_phone: Optional[str] = Field(None, description="Used when type='vcard'.")
    vcard_email: Optional[str] = Field(None, description="Used when type='vcard'.")
    vcard_org: Optional[str] = Field(None, description="Used when type='vcard'.")
    fg_color: str = Field("#000000", description="Foreground color as a hex code, e.g. #000000. PNG only - SVG output ignores this.")
    bg_color: str = Field("#ffffff", description="Background color as a hex code, e.g. #ffffff. PNG only - SVG output ignores this.")


class QRCodeOut(BaseModel):
    id: int
    type: str
    link_id: Optional[int] = None
    fg_color: str
    bg_color: str
    created_at: datetime
    image_url: str = Field(..., description="Fetch the rendered image (PNG) from this URL.")
    svg_url: str = Field(..., description="Fetch the rendered image (SVG) from this URL.")

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Must be unique.")
    email: Optional[str] = Field(None, description="Optional, must be unique if given.")
    password: Optional[str] = Field(
        None, min_length=8,
        description="Omit to auto-generate a random password, returned once in the response. "
                    "Use this when a panel/app is provisioning the account on a user's behalf.",
    )
    role: str = Field("customer", description="'customer' or 'admin'. Defaults to 'customer'.")


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    generated_password: Optional[str] = Field(
        None, description="Only present in the response right after creation, if no password was supplied. Not recoverable afterward - store it now."
    )

    model_config = {"from_attributes": True}
