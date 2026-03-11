"""
认证 API 路由
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.models import AdminUser, get_db
from schemas.schemas import LoginRequest, LoginResponse, TokenResponse, UserInfo, MessageResponse
from utils.auth import verify_password, create_access_token, get_current_admin

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(
        AdminUser.username == req.username,
        AdminUser.is_active == 1,
    ).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token({"sub": str(user.id)})
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    user.last_login = now
    user.login_count = (user.login_count or 0) + 1
    db.commit()

    from config.settings import settings
    return LoginResponse(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserInfo(id=user.id, username=user.username, role=user.role or "admin"),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: AdminUser = Depends(get_current_admin)):
    token = create_access_token({"sub": str(current_user.id)})
    from config.settings import settings
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(_: AdminUser = Depends(get_current_admin)):
    return MessageResponse(message="登出成功")
