from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

COOKIE_NAME = "refreshToken"


def set_refresh_cookie(response: Response, token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # set True in production (HTTPS)
        max_age=security.REFRESH_DAYS * 24 * 60 * 60,
    )


@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(data: schemas.RegisterRequest, db: Session = Depends(get_db)):
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
    return user


@router.post("/login", response_model=schemas.TokenResponse)
def login(data: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email.lower()).first()

    if not user or not security.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = security.create_access_token(user.id, user.role)
    refresh_token = security.create_refresh_token(user.id)

    user.refresh_token = refresh_token
    db.commit()

    set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "user": user}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/refresh")
def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = security.decode_refresh_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.get(models.User, int(payload["sub"]))

    # The cookie must match the one saved in the database
    if not user or user.refresh_token != refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    # Rotation: issue a new refresh token, the old one stops working
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
    return {"message": "Logged out"}