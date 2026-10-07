"""
Public "check before you click" page, same idea as b2n.ir's preview tool.
Shows where a short code leads without triggering the tracked redirect -
so checking a link never inflates its click count or logs a fake visit.
No auth required: this is meant to be usable by whoever received the
link, the same way the real redirect at /r/{code} is already public.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud

router = APIRouter(tags=["preview"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/preview/{code}")
def preview_link(code: str, request: Request, db: Session = Depends(get_db)):
    link = crud.get_link_by_code(db, code)
    return templates.TemplateResponse(
        request, "preview.html", {"code": code, "link": link}
    )
