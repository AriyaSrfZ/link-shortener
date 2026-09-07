"""
One-time migration for the multi-tenant upgrade. Safe to run multiple
times (every step checks before acting). Run this once after pulling
the multi-tenant code, before starting the app:

    python3 -m scripts.migrate_multi_tenant

What it does:
1. Creates the `users` table (new - via normal SQLAlchemy create_all).
2. Adds an `owner_id` column to the existing `links` table, if missing
   (SQLite can add a column but not a real foreign key constraint after
   the fact - that's fine, the ORM relationship still works, SQLite
   just won't enforce it at the DB level).
3. Creates a bootstrap admin user from ADMIN_USERNAME/ADMIN_PASSWORD in
   .env, if no admin exists yet.
4. Assigns every existing link with no owner to that admin account.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from passlib.context import CryptContext

from app.database import Base, engine, SessionLocal
from app.config import settings
from app.models import User, Link  # noqa: F401 (imported so create_all sees them)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def main():
    print("Creating any missing tables (users, etc.)...")
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        if not column_exists(conn, "links", "owner_id"):
            print("Adding owner_id column to links table...")
            conn.execute(text("ALTER TABLE links ADD COLUMN owner_id INTEGER"))
            conn.commit()
        else:
            print("owner_id column already exists, skipping.")

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print(f"Creating bootstrap admin user '{settings.admin_username}'...")
            admin = User(
                username=settings.admin_username,
                password_hash=pwd_context.hash(settings.admin_password),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            print(f"Admin user already exists: '{admin.username}'.")

        orphaned = db.query(Link).filter(Link.owner_id.is_(None)).all()
        if orphaned:
            print(f"Assigning {len(orphaned)} existing link(s) to admin...")
            for link in orphaned:
                link.owner_id = admin.id
            db.commit()
        else:
            print("No orphaned links to assign.")

        print("Migration complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
