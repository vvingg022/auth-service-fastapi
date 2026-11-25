import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..email_utils import send_reset_email
from ..limiter import limiter
from ..logger import log_event

router = APIRouter(prefix="/api/auth", tags=["Password"])

RESET_MINUTES = int(os.getenv("RESET_TOKEN_MINUTES", 30))


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    # Fast hash is fine here: the token is long and random, unlike a password
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/forgot-password", response_model=schemas.MessageResponse)
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    data: schemas.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = data.email.lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    if user:
        # Only one active reset token per user
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id
        ).delete()

        raw_token = secrets.token_urlsafe(32)
        db.add(
            models.PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=utc_now() + timedelta(minutes=RESET_MINUTES),
            )
        )
        db.commit()

        # Sent in the background so the response is instant either way
        background_tasks.add_task(send_reset_email, user.email, raw_token)
        log_event("password_reset_requested", user_id=user.id, ip=client_ip(request))
    else:
        log_event("password_reset_unknown_email", "warning", ip=client_ip(request))

    # Same answer whether or not the email exists
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", response_model=schemas.MessageResponse)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    data: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)

    record = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token_hash == hash_token(data.token))
        .first()
    )

    if not record or record.expires_at < utc_now():
        if record:
            db.delete(record)  # expired tokens are cleaned up
            db.commit()
        log_event("password_reset_rejected", "warning", ip=ip)
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.get(models.User, record.user_id)

    user.password_hash = security.hash_password(data.new_password)
    user.refresh_token = None            # kicks out every existing session
    user.failed_login_attempts = 0       # clears any lockout
    user.locked_until = None

    # Single use: remove this token and any other for the user
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id
    ).delete()
    db.commit()

    log_event("password_reset_success", "warning", user_id=user.id, ip=ip)
    return {"message": "Password has been reset. Please log in."}