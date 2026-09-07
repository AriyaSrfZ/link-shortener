"""
Account provisioning API - for a trusted external system (a panel, an
app, a signup flow you own elsewhere) to create accounts on a user's
behalf, without them going through the public /signup form.

Admin-only (or API key, which is treated as admin - see auth.py). A
customer session cannot call this: self-service signup stays at /signup,
this is purely for server-to-server provisioning.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.schemas import UserCreate, UserOut
from app.routers.auth import require_admin_or_api_key, hash_password, CurrentUser

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post(
    "",
    response_model=UserOut,
    summary="Provision a user account",
    description=(
        "Creates a customer (or admin) account directly, bypassing /signup. "
        "Omit `password` to auto-generate one, returned once in `generated_password` - "
        "capture it immediately, it isn't recoverable afterward. "
        "Typical use: your own panel/app calls this when one of its users needs "
        "a link-shortener account, then either forwards the generated password "
        "to that user or immediately has them set their own."
    ),
    responses={400: {"description": "Username or email already taken, or invalid role"}},
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin_or_api_key),
):
    if payload.role not in ("customer", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'customer' or 'admin'.")
    if crud.username_taken(db, payload.username):
        raise HTTPException(status_code=400, detail="That username is already taken.")
    if payload.email and crud.email_taken(db, payload.email):
        raise HTTPException(status_code=400, detail="That email is already registered.")

    generated_password = None
    plain_password = payload.password
    if not plain_password:
        generated_password = secrets.token_urlsafe(12)
        plain_password = generated_password

    user = crud.create_user(
        db,
        username=payload.username,
        password_hash=hash_password(plain_password),
        email=payload.email,
        role=payload.role,
    )

    return UserOut(
        id=user.id, username=user.username, email=user.email, role=user.role,
        is_active=user.is_active, created_at=user.created_at,
        generated_password=generated_password,
    )
