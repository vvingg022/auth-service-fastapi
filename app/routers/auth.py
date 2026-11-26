import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..dependencies import get_current_user
from ..limiter import limiter
from ..logger import log_event
from ..middleware import IS_PRODUCTION

router = APIRouter(prefix="/api/auth", tags=["Auth"])

COOKIE_NAME = "refreshToken"
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


def utc_now() -> datetime:
    # SQLite stores naive datetimes, so we keep everything as naive UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def set_refresh_cookie(response: Response, token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=IS_PRODUCTION,  # True on the live HTTPS site
        max_age=security.REFRESH_DAYS * 24 * 60 * 60,
    )


@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, data: schemas.RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.lower()

    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = models.User(
        name=data.name,
        email=email,
        password_hash=security.hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_event("register_success", user_id=user.id, ip=client_ip(request))
    return user


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    data: schemas.LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    email = data.email.lower()
    now = utc_now()

    user = db.query(models.User).filter(models.User.email == email).first()

    # 1. Locked accounts are refused, even with the right password
    if user and user.locked_until and user.locked_until > now:
        minutes_left = math.ceil((user.locked_until - now).total_seconds() / 60)
        log_event("login_blocked_locked", "warning", user_id=user.id, ip=ip)
        raise HTTPException(
            status_code=423,
            detail=f"Account locked. Try again in {minutes_left} minute(s).",
        )

    # 2. Wrong credentials
    if not user or not security.verify_password(data.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_login_attempts = 0
                db.commit()
                log_event(
                    "account_locked", "warning",
                    user_id=user.id, ip=ip, minutes=LOCK_MINUTES,
                )
                raise HTTPException(
                    status_code=423,
                    detail=f"Too many failed attempts. Account locked for {LOCK_MINUTES} minutes.",
                )

            db.commit()
            log_event(
                "login_failed", "warning",
                user_id=user.id, ip=ip, attempts=user.failed_login_attempts,
            )
        else:
            log_event("login_failed_unknown_email", "warning", email=email, ip=ip)

        # Same message for wrong email and wrong password
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # 3. Success: reset the counter and issue tokens
    user.failed_login_attempts = 0
    user.locked_until = None

    access_token = security.create_access_token(user.id, user.role)
    refresh_token = security.create_refresh_token(user.id)
    user.refresh_token = refresh_token
    db.commit()

    log_event("login_success", user_id=user.id, ip=ip)

    set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "user": user}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = security.decode_refresh_token(refresh_token)
    except jwt.ExpiredSignatureError:
        log_event("refresh_rejected", "warning", reason="expired", ip=ip)
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        log_event("refresh_rejected", "warning", reason="invalid", ip=ip)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.get(models.User, int(payload["sub"]))

    if not user or user.refresh_token != refresh_token:
        # A valid but revoked token being used can mean a stolen token
        log_event(
            "refresh_rejected", "warning",
            reason="revoked", user_id=payload["sub"], ip=ip,
        )
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    new_access = security.create_access_token(user.id, user.role)
    new_refresh = security.create_refresh_token(user.id)
    user.refresh_token = new_refresh
    db.commit()

    set_refresh_cookie(response, new_refresh)
    return {"access_token": new_access}


@router.post("/logout")
def logout(
    response: Response,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.refresh_token = None
    db.commit()
    response.delete_cookie(COOKIE_NAME)

    log_event("logout", user_id=current_user.id)
    return {"message": "Logged out"}