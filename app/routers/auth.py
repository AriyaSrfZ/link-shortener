"""
Minimal session-based auth. Single admin account (from .env), no user table -
this is a personal/local tool, not a multi-tenant product. Session state is
stored in a signed cookie via Starlette's SessionMiddleware (set up in main.py).
"""

from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

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


def require_login(request: Request):
    """FastAPI dependency: raises 401 JSON error if no active session. Use on API routes."""
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=401, detail="Login required")
    return True


def require_login_ui(request: Request):
    """Same check, but for HTML pages - redirects to /login instead of a 401 JSON error."""
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
