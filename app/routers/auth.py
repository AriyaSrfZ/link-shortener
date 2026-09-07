"""
Auth for this app has three pieces:

1. Session cookie - for the HTML dashboard. Set at /login after checking
   a username/password against the `users` table (hashed with bcrypt).
   Any logged-in user (admin or customer) gets a session; role determines
   what they can see once logged in (enforced in dashboard.py/links.py).

2. Signup - customers self-register via /signup. Always creates a
   "customer" role account; there is no way to create an admin through
   this form. The bootstrap admin account is created once by
   scripts/migrate_multi_tenant.py from .env credentials.

3. API key header (X-API-Key) - for programmatic access from an external
   app. Configured via API_KEY in .env. Requests authenticated this way
   are treated as full admin access (they represent your own app/service
   calling its own API, not a specific customer) - there is no per-customer
   API key in this version.

get_current_user() is the shared building block: it resolves either an
API key or a session cookie down to a User row (or a synthetic "API key"
admin-equivalent), and every route that needs to know "who is asking"
uses it instead of a bare True/False check.
"""

from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException, Form, Header
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class CurrentUser:
    """Normalizes 'who is making this request' across the two auth paths.
    is_admin=True means: see/manage everything, no ownership filtering."""
    id: Optional[int]
    username: str
    is_admin: bool


class NotLoggedInUI(Exception):
    """Raised by UI routes when there is no session. Handled in main.py to
    return a redirect instead of a raw error page."""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
) -> Optional[CurrentUser]:
    """Returns a CurrentUser if authenticated via either path, else None.
    Does not raise - callers decide what "not authenticated" means for them."""
    if settings.api_key and x_api_key == settings.api_key:
        return CurrentUser(id=None, username="api-key", is_admin=True)

    user_id = request.session.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
        if user:
            return CurrentUser(id=user.id, username=user.username, is_admin=user.is_admin)

    return None


def require_login(current_user: Optional[CurrentUser] = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency for the JSON API. Raises 401 if not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="Login required. Send a valid X-API-Key header, or log in via /login for a session.",
        )
    return current_user


def require_login_ui(
    current_user: Optional[CurrentUser] = Depends(get_current_user),
) -> CurrentUser:
    """Same check, but for HTML pages - redirects to /login instead of a 401 JSON error."""
    if current_user is None:
        raise NotLoggedInUI()
    return current_user


def require_admin_ui(current_user: CurrentUser = Depends(require_login_ui)) -> CurrentUser:
    """For admin-only pages (user management). Raises 403 for a logged-in customer."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only.")
    return current_user


def require_admin_or_api_key(current_user: CurrentUser = Depends(require_login)) -> CurrentUser:
    """For admin-only JSON API routes (account provisioning). Raises 403 for
    an authenticated customer session - this must not be callable by a
    customer on their own account, only by an admin or a trusted API key."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/signup")
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request, "error": None, "form": {}})


@router.post("/signup")
def signup_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    error = None
    if len(username) < 3:
        error = "Username must be at least 3 characters."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != password_confirm:
        error = "Passwords do not match."
    elif db.query(User).filter(User.username == username).first():
        error = "That username is already taken."
    elif email and db.query(User).filter(User.email == email).first():
        error = "That email is already registered."

    if error:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": error, "form": {"username": username, "email": email}},
            status_code=400,
        )

    user = User(
        username=username,
        email=email or None,
        password_hash=hash_password(password),
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
