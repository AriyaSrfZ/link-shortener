"""
Builds the raw string a QR code should encode (depends on type), and
renders it to PNG or SVG bytes. Pure functions, no DB access - keeps
this independently testable and reusable from both the API and any
future CLI/script.
"""

import re
from io import BytesIO
from typing import Optional

import qrcode
import qrcode.image.svg
from qrcode.constants import ERROR_CORRECT_M

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def is_valid_hex_color(value: str) -> bool:
    return bool(HEX_COLOR_PATTERN.match(value))


def _escape_vcard(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def build_text_payload(text: str) -> str:
    return text


def build_wifi_payload(ssid: str, password: str, security: str = "WPA", hidden: bool = False) -> str:
    """Standard WIFI: URI format, recognized by phone camera apps."""
    security = security.upper() if security.upper() in ("WPA", "WEP") else "nopass"
    ssid_esc = ssid.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    pwd_esc = "" if security == "nopass" else password.replace("\\", "\\\\").replace(";", "\\;")
    hidden_str = "true" if hidden else "false"
    return f"WIFI:T:{security};S:{ssid_esc};P:{pwd_esc};H:{hidden_str};;"


def build_vcard_payload(name: str, phone: str = "", email: str = "", org: str = "") -> str:
    """vCard 3.0 - the widely-supported format for QR contact cards."""
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:;{_escape_vcard(name)};;;", f"FN:{_escape_vcard(name)}"]
    if org:
        lines.append(f"ORG:{_escape_vcard(org)}")
    if phone:
        lines.append(f"TEL:{_escape_vcard(phone)}")
    if email:
        lines.append(f"EMAIL:{_escape_vcard(email)}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def generate_png(data: str, fg_color: str = "#000000", bg_color: str = "#ffffff", box_size: int = 10, border: int = 4) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg_color, back_color=bg_color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_svg(data: str, box_size: int = 10, border: int = 4) -> bytes:
    """SVG output doesn't support custom fill/back colors via this library
    without post-processing the XML, so it's always rendered black-on-
    transparent - fine for print, where color usually doesn't matter anyway."""
    qr = qrcode.QRCode(image_factory=qrcode.image.svg.SvgPathImage, error_correction=ERROR_CORRECT_M, box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue()
