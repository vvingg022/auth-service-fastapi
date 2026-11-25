import os
import secrets

from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..limiter import limiter
from ..logger import log_event
from .auth import client_ip, set_refresh_cookie

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

router = APIRouter(prefix="/api/auth/google", tags=["Google"])

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
@limiter.limit("10/minute")
async def google_login(request: Request):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI):
        raise HTTPException(status_code=503, detail="Google login is not configured")

    # Sends the browser to Google and stores a random "state" in the session cookie
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/callback", response_model=schemas.TokenResponse)
@limiter.limit("10/minute")
async def google_callback(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)

    # 1. Swap the code for the user's identity (also checks the "state")
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        log_event("google_login_failed", "warning", reason=exc.error, ip=ip)
        raise HTTPException(
            status_code=400, detail="Google sign-in failed or was cancelled"
        )

    info = token.get("userinfo")

    # 2. Google must vouch that the user owns this email
    if not info or not info.get("email") or not info.get("email_verified"):
        log_event("google_login_failed", "warning", reason="unverified_email", ip=ip)
        raise HTTPException(
            status_code=400, detail="Your Google account has no verified email"
        )

    google_id = info["sub"]
    email = info["email"].lower()
    name = info.get("name") or email.split("@")[0]

    # 3. Returning Google user?
    link = (
        db.query(models.OAuthAccount)
        .filter(
            models.OAuthAccount.provider == "google",
            models.OAuthAccount.provider_user_id == google_id,
        )
        .first()
    )

    if link:
        user = db.get(models.User, link.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="Account no longer exists")
    else:
        # 4. Same email already registered with a password: do NOT merge silently
        if db.query(models.User).filter(models.User.email == email).first():
            log_event("google_login_blocked_existing_email", "warning", ip=ip)
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please log in with your password.",
            )

        # 5. New user: random unusable password, linked to this Google account
        user = models.User(
            name=name,
            email=email,
            password_hash=security.hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.flush()  # gives the user an id before we link it
        db.add(
            models.OAuthAccount(
                user_id=user.id, provider="google", provider_user_id=google_id
            )
        )
        db.commit()
        db.refresh(user)
        log_event("google_account_created", user_id=user.id, ip=ip)

    # 6. Issue OUR tokens, same as a normal login
    access_token = security.create_access_token(user.id, user.role)
    refresh_token = security.create_refresh_token(user.id)
    user.refresh_token = refresh_token
    db.commit()

    set_refresh_cookie(response, refresh_token)
    log_event("google_login_success", user_id=user.id, ip=ip)

    return {"access_token": access_token, "user": user}