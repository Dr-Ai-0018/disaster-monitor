"""
创建 GPU 服务器 API Token
"""
import sqlite3
import secrets
import json
from datetime import datetime


def create_api_token(
    name: str,
    description: str = "",
    db_path: str = "database/disaster.db",
) -> str:
    """创建 API Token，返回 token 字符串"""
    token = secrets.token_urlsafe(32)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now = int(datetime.now().timestamp() * 1000)
    scopes = json.dumps(["tasks.read", "tasks.update"])

    cursor.execute(
        """
        INSERT INTO api_tokens (token, name, description, scopes, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (token, name, description, scopes, 1, now),
    )

    conn.commit()
    conn.close()

    print(f"✅ API Token 创建完成")
    print(f"   名称: {name}")
    print(f"   Token: {token}")
    print(f"   ⚠️  请妥善保管 Token，不会再次显示！")

    return token


if __name__ == "__main__":
    create_api_token(name="GPU-Server-1", description="内网GPU服务器访问令牌")
