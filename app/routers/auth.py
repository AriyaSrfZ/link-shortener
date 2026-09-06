"""
Auth for this app has two independent paths:
1. Session cookie - for the HTML dashboard, set at /login. Browser-only.
2. API key header (X-API-Key) - for programmatic access from another app,
   script, or service. No login flow needed; just send the header on every
   request. Configured via API_KEY in .env; leave it blank to disable this
   path entirely and require session login even for the JSON API.

require_login() (used on the JSON API routes) accepts EITHER. This lets
you use the same endpoints from a browser session (e.g. testing in /docs
while logged into the dashboard) and from an external app (via API key),
without maintaining two separate route sets.
"""

from fastapi import APIRouter, Depends, Request, HTTPException, Form, Header
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from typing import Optional

from app.config import settings

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _check_credentials(username: str, password: str) -> bool:
    # Admin credentials come from .env as plaintext for simplicity in a local
    # tool. To harden: store a bcrypt hash in .env instead and verify with
    # pwd_context.verify(password, settings.admin_password_hash).
    return username == settings.admin_username and password == settings.admin_password


class NotLoggedInUI(Exception):
    """Raised by UI routes when there is no session. Handled in main.py to
    return a redirect instead of a raw error page."""


def require_login(request: Request, x_api_key: Optional[str] = Header(None)):
    """FastAPI dependency for the JSON API. Accepts either a valid session
    cookie OR a matching X-API-Key header. Raises 401 if neither is present.
    Use this on any route meant to be callable from an external app."""
    if request.session.get("logged_in"):
        return True
    if settings.api_key and x_api_key == settings.api_key:
        return True
    raise HTTPException(
        status_code=401,
        detail="Login required. Send a valid X-API-Key header, or log in via /login for a session.",
    )


def require_login_ui(request: Request):
    """Same check, but for HTML pages - redirects to /login instead of a 401 JSON error.
    API key auth does not apply here; the dashboard is browser-only."""
    if not request.session.get("logged_in"):
        raise NotLoggedInUI()
    return True


@router.get("/login")
def login_page(request: Request):
    if request.session.get("logged_in"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if _check_credentials(username, password):
        request.session["logged_in"] = True
        request.session["username"] = username
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password."},
        status_code=401,
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
