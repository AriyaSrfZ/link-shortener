"""
Sets required environment variables before any test module imports
`app.*`. Settings values are read once at import time (see app/config.py),
so this must run first - pytest guarantees conftest.py loads before any
test file in the same directory.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")
os.environ.setdefault("BASE_URL", "http://testserver")
os.environ.setdefault("API_KEY", "test-api-key-123")
os.environ.setdefault("RATE_LIMIT_LOGIN", "1000/minute")
os.environ.setdefault("RATE_LIMIT_REGISTER", "1000/minute")

import pytest
from passlib.context import CryptContext


@pytest.fixture(scope="session", autouse=True)
def _fast_password_hashing():
    from app.routers import auth
    original_context = auth.pwd_context
    auth.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)
    yield
    auth.pwd_context = original_context

