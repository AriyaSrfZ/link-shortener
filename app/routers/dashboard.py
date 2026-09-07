"""
Server-rendered dashboard. Every route here is ownership-aware:
admins see and manage everything (plus the customer-management page),
customers only ever see links they created themselves.
"""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import crud, analytics
from app.routers.auth import require_login_ui, require_admin_ui, CurrentUser
router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def dashboard_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    links = crud.list_links_for_user(db, current_user)
    rows = [
        {
            "link": link,
            "short_url": f"{settings.base_url}/r/{link.short_code}",
            "click_count": crud.count_clicks(db, link.id),
        }
        for link in links
    ]
    owner_id = None if current_user.is_admin else current_user.id
    summary = analytics.total_clicks_summary(db, owner_id=owner_id)
    daily = analytics.clicks_per_day(db, owner_id=owner_id, days=14)
    referrers = analytics.top_referrers(db, owner_id=owner_id)
    devices = analytics.device_breakdown(db, owner_id=owner_id)
    countries = analytics.top_countries(db, owner_id=owner_id)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "rows": rows,
            "summary": summary,
            "daily": daily,
            "referrers": referrers,
            "devices": devices,
            "countries": countries,
            "current_user": current_user,
        },
    )


@router.get("/new")
def new_link_form(
    request: Request,
    current_user: CurrentUser = Depends(require_login_ui),
):
    return templates.TemplateResponse(
        "create.html", {"request": request, "error": None, "form": {}, "current_user": current_user}
    )


@router.post("/new")
def new_link_submit(
    request: Request,
    long_url: str = Form(...),
    utm_source: str = Form(...),
    utm_medium: str = Form(...),
    utm_campaign: str = Form(...),
    utm_term: str = Form(""),
    utm_content: str = Form(""),
    custom_code: str = Form(""),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    try:
        link = crud.create_link(
            db,
            long_url=long_url,
            owner_id=current_user.id,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_term=utm_term or None,
            utm_content=utm_content or None,
            custom_code=custom_code or None,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "create.html",
            {
                "request": request,
                "error": str(exc),
                "current_user": current_user,
                "form": {
                    "long_url": long_url,
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "utm_campaign": utm_campaign,
                    "utm_term": utm_term,
                    "utm_content": utm_content,
                    "custom_code": custom_code,
                },
            },
            status_code=400,
        )
    return RedirectResponse(f"/dashboard/{link.id}", status_code=303)


# ---- QR codes -----------------------------------------------------------

@router.get("/qrcodes")
def qrcodes_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    codes = crud.list_qr_codes_for_user(db, current_user)
    my_links = crud.list_links_for_user(db, current_user)
    return templates.TemplateResponse(
        "qrcodes.html",
        {"request": request, "codes": codes, "my_links": my_links, "current_user": current_user},
    )


@router.post("/qrcodes/new")
def qrcodes_create(
    request: Request,
    qr_type: str = Form(...),
    link_id: str = Form(""),
    text: str = Form(""),
    wifi_ssid: str = Form(""),
    wifi_password: str = Form(""),
    wifi_security: str = Form("WPA"),
    wifi_hidden: str = Form(""),
    vcard_name: str = Form(""),
    vcard_phone: str = Form(""),
    vcard_email: str = Form(""),
    vcard_org: str = Form(""),
    fg_color: str = Form("#000000"),
    bg_color: str = Form("#ffffff"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    import json as _json

    try:
        if qr_type == "link":
            if not link_id:
                raise ValueError("Pick a link.")
            link = crud.get_link_for_user(db, int(link_id), current_user)
            if not link:
                raise ValueError("That link isn't yours.")
            payload_json, resolved_link_id = None, int(link_id)
        elif qr_type == "text":
            if not text:
                raise ValueError("Text is required.")
            payload_json, resolved_link_id = _json.dumps({"text": text}), None
        elif qr_type == "wifi":
            if not wifi_ssid:
                raise ValueError("Network name is required.")
            payload_json, resolved_link_id = _json.dumps({
                "ssid": wifi_ssid, "password": wifi_password,
                "security": wifi_security, "hidden": bool(wifi_hidden),
            }), None
        elif qr_type == "vcard":
            if not vcard_name:
                raise ValueError("Contact name is required.")
            payload_json, resolved_link_id = _json.dumps({
                "name": vcard_name, "phone": vcard_phone, "email": vcard_email, "org": vcard_org,
            }), None
        else:
            raise ValueError("Unknown QR type.")

        crud.create_qr_code(
            db, owner_id=current_user.id, qr_type=qr_type, link_id=resolved_link_id,
            payload=payload_json, fg_color=fg_color or "#000000", bg_color=bg_color or "#ffffff",
        )
    except ValueError as exc:
        codes = crud.list_qr_codes_for_user(db, current_user)
        my_links = crud.list_links_for_user(db, current_user)
        return templates.TemplateResponse(
            "qrcodes.html",
            {"request": request, "codes": codes, "my_links": my_links, "current_user": current_user, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/dashboard/qrcodes", status_code=303)


@router.get("/{link_id}")
def link_detail(
    link_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    link = crud.get_link_for_user(db, link_id, current_user)
    if not link:
        return RedirectResponse("/dashboard", status_code=303)
    clicks = sorted(link.clicks, key=lambda c: c.clicked_at, reverse=True)
    daily = analytics.clicks_per_day(db, link_id=link_id, days=14)
    referrers = analytics.top_referrers(db, link_id=link_id)
    devices = analytics.device_breakdown(db, link_id=link_id)
    countries = analytics.top_countries(db, link_id=link_id)
    return templates.TemplateResponse(
        "link_detail.html",
        {
            "request": request,
            "link": link,
            "short_url": f"{settings.base_url}/r/{link.short_code}",
            "clicks": clicks,
            "daily": daily,
            "referrers": referrers,
            "devices": devices,
            "countries": countries,
            "current_user": current_user,
        },
    )


@router.post("/{link_id}/delete")
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    crud.delete_link_for_user(db, link_id, current_user)
    return RedirectResponse("/dashboard", status_code=303)


# ---- Admin: customer management ---------------------------------------

@router.get("/admin/users")
def users_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin_ui),
):
    customers = crud.list_customers(db)
    rows = [
        {"user": u, "link_count": crud.count_links_for_owner(db, u.id)}
        for u in customers
    ]
    return templates.TemplateResponse(
        "users.html", {"request": request, "rows": rows, "current_user": current_user}
    )


@router.post("/admin/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin_ui),
):
    user = crud.get_user_by_id(db, user_id)
    if user:
        crud.set_user_active(db, user_id, not user.is_active)
    return RedirectResponse("/dashboard/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/delete")
def delete_user_route(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin_ui),
):
    crud.delete_user(db, user_id)
    return RedirectResponse("/dashboard/admin/users", status_code=303)


@router.post("/qrcodes/{qr_id}/delete")
def qrcodes_delete(
    qr_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_login_ui),
):
    crud.delete_qr_code_for_user(db, qr_id, current_user)
    return RedirectResponse("/dashboard/qrcodes", status_code=303)
