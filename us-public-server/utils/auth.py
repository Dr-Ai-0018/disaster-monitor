"""
JWT 和 API Token 认证工具
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session

from config.settings import settings
from models.models import AdminUser, ApiToken, get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


# ──────────────────────────────────────────
# 密码工具
# ──────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ──────────────────────────────────────────
# JWT
# ──────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────
# 依赖项：管理员 JWT
# ──────────────────────────────────────────

def get_current_admin(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证 Token")
    payload = decode_token(token)
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 数据无效")

    user = db.query(AdminUser).filter(AdminUser.id == int(user_id), AdminUser.is_active == 1).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


# ──────────────────────────────────────────
# 依赖项：GPU API Token
# ──────────────────────────────────────────

def get_api_token_entity(
    token: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ApiToken:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 X-API-Token 请求头")

    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    entity = db.query(ApiToken).filter(
        ApiToken.token == token,
        ApiToken.is_active == 1,
    ).first()

    if not entity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Token 无效或已禁用")

    if entity.expires_at and entity.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Token 已过期")

    # 更新使用统计
    entity.last_used = now
    entity.usage_count = (entity.usage_count or 0) + 1
    db.commit()

    return entity
