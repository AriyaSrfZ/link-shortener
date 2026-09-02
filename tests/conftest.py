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
