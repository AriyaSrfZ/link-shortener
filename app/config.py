"""
Central configuration for the app.
Everything reads from environment variables (via .env in local dev),
so no secrets or environment-specific values live in the code.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    base_url: str = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin")
    shortcode_length: int = int(os.getenv("SHORTCODE_LENGTH", "6"))
    api_key: str = os.getenv("API_KEY", "")


settings = Settings()
