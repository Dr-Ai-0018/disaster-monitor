from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.settings import settings
from models.models import AdminUser, get_db
from schemas.schemas import LoginRequest, TokenResponse
from utils.auth import create_access_token, get_current_admin, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.username == req.username, AdminUser.is_active == 1).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token({"sub": str(user.id)})
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    user.last_login = now
    user.login_count = (user.login_count or 0) + 1
    db.commit()
    return TokenResponse(access_token=token, expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: AdminUser = Depends(get_current_admin)):
    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(access_token=token, expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)
