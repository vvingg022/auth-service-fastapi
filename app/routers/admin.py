from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import require_role
from ..logger import log_event

admin_only = require_role("admin")

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(admin_only)],
)


@router.get("/users", response_model=List[schemas.UserOut])
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.User)
        .order_by(models.User.id)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )


@router.patch("/users/{user_id}/role", response_model=schemas.UserOut)
def change_role(
    user_id: int,
    data: schemas.RoleUpdate,
    current_admin: models.User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = data.role
    user.refresh_token = None  # forces re-login, so the new role applies cleanly
    db.commit()
    db.refresh(user)

    log_event(
        "role_changed", "warning",
        admin_id=current_admin.id, target_user_id=user.id, new_role=data.role,
    )
    return user


@router.post("/users/{user_id}/unlock", response_model=schemas.UserOut)
def unlock_user(
    user_id: int,
    current_admin: models.User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)

    log_event(
        "account_unlocked",
        admin_id=current_admin.id, target_user_id=user.id,
    )
    return user