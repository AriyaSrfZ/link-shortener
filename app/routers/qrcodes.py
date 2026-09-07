"""
JSON API for QR codes, same ownership model as links.py: a customer only
ever sees/manages their own QR codes; admin/API-key sees everything.

Four types:
  - link:  encodes an existing short link's URL. "Dynamic" - editing the
           link's destination changes what scanning it does, no reprint.
  - text:  encodes arbitrary text. Not clickable/trackable.
  - wifi:  encodes network credentials in the standard WIFI: URI format
           phone cameras recognize.
  - vcard: encodes a contact card in vCard 3.0 format.

Image endpoints (/image, /svg) additionally accept an `api_key` query
parameter as an alternative to the X-API-Key header, since an <img src=...>
tag can't set custom headers. This is less secure than the header (the
key ends up in browser history / server logs / the Referer header sent
to whatever page embeds the image) - use the header wherever the caller
can. Documented in docs/API.md.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import crud
from app.models import QRCode
from app.schemas import QRCodeCreate, QRCodeOut
from app.routers.auth import require_login, get_current_user, CurrentUser
from app.utils import qrgen

router = APIRouter(prefix="/api/qrcodes", tags=["qrcodes"])

_UNAUTHORIZED = {
    401: {
        "description": "Missing or invalid credentials",
        "content": {"application/json": {"example": {"detail": "Login required."}}},
    }
}
_NOT_FOUND = {404: {"description": "QR code not found (or not owned by you)"}}


def _build_payload_and_validate(payload: QRCodeCreate, db: Session, current_user: CurrentUser) -> tuple[Optional[str], Optional[int]]:
    """Validates the type-specific fields and returns (payload_json, link_id)
    ready to store. Raises ValueError with a user-facing message on bad input."""
    if payload.type == "link":
        if not payload.link_id:
            raise ValueError("link_id is required when type='link'.")
        link = crud.get_link_for_user(db, payload.link_id, current_user)
        if not link:
            raise ValueError("That link doesn't exist or isn't yours.")
        return None, payload.link_id

    if payload.type == "text":
        if not payload.text:
            raise ValueError("text is required when type='text'.")
        return json.dumps({"text": payload.text}), None

    if payload.type == "wifi":
        if not payload.wifi_ssid:
            raise ValueError("wifi_ssid is required when type='wifi'.")
        return json.dumps({
            "ssid": payload.wifi_ssid,
            "password": payload.wifi_password or "",
            "security": payload.wifi_security or "WPA",
            "hidden": bool(payload.wifi_hidden),
        }), None

    if payload.type == "vcard":
        if not payload.vcard_name:
            raise ValueError("vcard_name is required when type='vcard'.")
        return json.dumps({
            "name": payload.vcard_name,
            "phone": payload.vcard_phone or "",
            "email": payload.vcard_email or "",
            "org": payload.vcard_org or "",
        }), None

    raise ValueError("type must be one of: link, text, wifi, vcard.")


def _resolve_qr_data(qr: QRCode, db: Session) -> str:
    """Turns a stored QRCode row back into the actual string to encode."""
    if qr.type == "link":
        link = crud.get_link_by_id(db, qr.link_id)
        if not link:
            raise HTTPException(status_code=404, detail="The link this QR code points to was deleted.")
        return f"{settings.base_url}/r/{link.short_code}"

    data = json.loads(qr.payload or "{}")
    if qr.type == "text":
        return qrgen.build_text_payload(data.get("text", ""))
    if qr.type == "wifi":
        return qrgen.build_wifi_payload(data["ssid"], data.get("password", ""), data.get("security", "WPA"), data.get("hidden", False))
    if qr.type == "vcard":
        return qrgen.build_vcard_payload(data["name"], data.get("phone", ""), data.get("email", ""), data.get("org", ""))
    raise HTTPException(status_code=500, detail="Unknown QR code type in storage.")


def _to_qr_out(qr: QRCode) -> QRCodeOut:
    return QRCodeOut(
        id=qr.id,
        type=qr.type,
        link_id=qr.link_id,
        fg_color=qr.fg_color,
        bg_color=qr.bg_color,
        created_at=qr.created_at,
        image_url=f"{settings.base_url}/api/qrcodes/{qr.id}/image",
        svg_url=f"{settings.base_url}/api/qrcodes/{qr.id}/svg",
    )


def _auth_for_image(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None, description="Alternative to the X-API-Key header, for use in <img src> tags."),
) -> CurrentUser:
    """Same as require_login, but also accepts ?api_key= as a fallback for
    <img src="..."> tags, which can't set custom headers. Session cookies
    (e.g. the dashboard's own QR previews) work exactly as normal here."""
    effective_key = x_api_key or api_key
    current_user = get_current_user(request=request, db=db, x_api_key=effective_key)
    if current_user:
        return current_user
    raise HTTPException(status_code=401, detail="Login required. Send X-API-Key (header or ?api_key=), or log in for a session.")


@router.post(
    "",
    response_model=QRCodeOut,
    summary="Create a QR code",
    description=(
        "type='link' encodes an existing short link's URL (dynamic - editing the "
        "link's destination updates what scanning it does, no reprint needed). "
        "type='text'/'wifi'/'vcard' encode standalone content, not tied to a "
        "trackable link. See each field's description for which are required per type."
    ),
    responses={**_UNAUTHORIZED, 400: {"description": "Invalid input for the given type"}},
)
def create_qr_code(
    payload: QRCodeCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login),
):
    if not qrgen.is_valid_hex_color(payload.fg_color) or not qrgen.is_valid_hex_color(payload.bg_color):
        raise HTTPException(status_code=400, detail="fg_color and bg_color must be hex codes like #000000.")
    try:
        payload_json, link_id = _build_payload_and_validate(payload, db, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    owner_id = current_user.id
    if owner_id is None:
        # API-key requests aren't tied to a specific user row; attribute
        # ownership to the target link's owner if there is one, else refuse -
        # a standalone QR code needs *some* owner to belong to.
        if link_id:
            link = crud.get_link_by_id(db, link_id)
            owner_id = link.owner_id
        if owner_id is None:
            raise HTTPException(
                status_code=400,
                detail="Standalone QR codes (text/wifi/vcard) require a customer session, not an API key, since they need an owner.",
            )

    qr = crud.create_qr_code(
        db, owner_id=owner_id, qr_type=payload.type, link_id=link_id,
        payload=payload_json, fg_color=payload.fg_color, bg_color=payload.bg_color,
    )
    return _to_qr_out(qr)


@router.get("", response_model=list[QRCodeOut], summary="List QR codes")
def list_qr_codes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login),
):
    codes = crud.list_qr_codes_for_user(db, current_user, skip=skip, limit=limit)
    return [_to_qr_out(c) for c in codes]


@router.get("/{qr_id}", response_model=QRCodeOut, summary="Get one QR code's metadata", responses={**_UNAUTHORIZED, **_NOT_FOUND})
def get_qr_code(qr_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_login)):
    qr = crud.get_qr_code_for_user(db, qr_id, current_user)
    if not qr:
        raise HTTPException(status_code=404, detail="QR code not found")
    return _to_qr_out(qr)


@router.delete("/{qr_id}", summary="Delete a QR code", responses={**_UNAUTHORIZED, **_NOT_FOUND})
def delete_qr_code(qr_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_login)):
    if not crud.delete_qr_code_for_user(db, qr_id, current_user):
        raise HTTPException(status_code=404, detail="QR code not found")
    return {"ok": True}


@router.get(
    "/{qr_id}/image",
    summary="Get the QR code as a PNG image",
    description="Accepts X-API-Key header OR ?api_key= query param (for use in <img src>).",
    responses={**_UNAUTHORIZED, **_NOT_FOUND, 200: {"content": {"image/png": {}}}},
)
def get_qr_image_png(qr_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(_auth_for_image)):
    qr = crud.get_qr_code_for_user(db, qr_id, current_user)
    if not qr:
        raise HTTPException(status_code=404, detail="QR code not found")
    data = _resolve_qr_data(qr, db)
    png_bytes = qrgen.generate_png(data, fg_color=qr.fg_color, bg_color=qr.bg_color)
    return Response(content=png_bytes, media_type="image/png")


@router.get(
    "/{qr_id}/svg",
    summary="Get the QR code as an SVG image",
    description="Accepts X-API-Key header OR ?api_key= query param (for use in <img src>). Always black-on-transparent; fg/bg colors apply to PNG only.",
    responses={**_UNAUTHORIZED, **_NOT_FOUND, 200: {"content": {"image/svg+xml": {}}}},
)
def get_qr_image_svg(qr_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(_auth_for_image)):
    qr = crud.get_qr_code_for_user(db, qr_id, current_user)
    if not qr:
        raise HTTPException(status_code=404, detail="QR code not found")
    data = _resolve_qr_data(qr, db)
    svg_bytes = qrgen.generate_svg(data)
    return Response(content=svg_bytes, media_type="image/svg+xml")
