"""
Server-rendered dashboard: list links, create-link form, per-link detail
page with the click backtrace table. This is the primary UI - the JSON
API in routers/links.py covers the same actions for scripts/Postman.
"""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import crud
from app.routers.auth import require_login_ui

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def dashboard_home(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login_ui),
):
    links = crud.list_links(db)
    rows = [
        {
            "link": link,
            "short_url": f"{settings.base_url}/r/{link.short_code}",
            "click_count": crud.count_clicks(db, link.id),
        }
        for link in links
    ]
    return templates.TemplateResponse(
        "index.html", {"request": request, "rows": rows}
    )


@router.get("/new")
def new_link_form(
    request: Request,
    _: bool = Depends(require_login_ui),
):
    return templates.TemplateResponse(
        "create.html", {"request": request, "error": None, "form": {}}
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
    _: bool = Depends(require_login_ui),
):
    try:
        link = crud.create_link(
            db,
            long_url=long_url,
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


@router.get("/{link_id}")
def link_detail(
    link_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login_ui),
):
    link = crud.get_link_by_id(db, link_id)
    if not link:
        return RedirectResponse("/dashboard", status_code=303)
    clicks = sorted(link.clicks, key=lambda c: c.clicked_at, reverse=True)
    return templates.TemplateResponse(
        "link_detail.html",
        {
            "request": request,
            "link": link,
            "short_url": f"{settings.base_url}/r/{link.short_code}",
            "clicks": clicks,
        },
    )


@router.post("/{link_id}/delete")
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login_ui),
):
    crud.delete_link(db, link_id)
    return RedirectResponse("/dashboard", status_code=303)
