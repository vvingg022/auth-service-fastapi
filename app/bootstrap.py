import os

from . import models, security
from .database import SessionLocal
from .logger import log_event


def ensure_admin() -> None:
    """Creates the first admin from ADMIN_EMAIL / ADMIN_PASSWORD, only if no admin exists."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")

    if not email or not password:
        return

    if len(password) < 8:
        log_event("bootstrap_admin_skipped", "warning", reason="password_too_short")
        return

    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.role == "admin").first():
            return  # an admin already exists, so do nothing

        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.role = "admin"
        else:
            db.add(
                models.User(
                    name="Admin",
                    email=email,
                    password_hash=security.hash_password(password),
                    role="admin",
                )
            )
        db.commit()
        log_event("bootstrap_admin_created")
    finally:
        db.close()