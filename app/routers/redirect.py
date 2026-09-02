"""
The public-facing redirect endpoint. No auth here - this is the link
people actually click. Every hit is logged before the redirect fires.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud

router = APIRouter(tags=["redirect"])


def _client_ip(request: Request) -> str:
    # Respect X-Forwarded-For when running behind a reverse proxy (nginx, etc.)
    # in the future deployment; falls back to the direct connection IP locally.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/r/{code}")
def redirect_short_link(code: str, request: Request, db: Session = Depends(get_db)):
    link = crud.get_link_by_code(db, code)

    if not link or not link.is_active:
        return RedirectResponse("/dashboard", status_code=303)

    crud.log_click(
        db,
        link_id=link.id,
        ip_address=_client_ip(request),
        referrer=request.headers.get("referer"),
        user_agent_raw=request.headers.get("user-agent"),
    )

    return RedirectResponse(link.final_url, status_code=302)
