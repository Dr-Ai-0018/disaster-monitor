"""
创建 GPU 服务器 API Token
"""
import sqlite3
import secrets
import json
from datetime import datetime
from typing import Dict

from config.settings import settings


def create_api_token(
    name: str = None,
    description: str = None,
    db_path: str = None,
    token_value: str = None,
    print_token: bool = False,
) -> Dict[str, str]:
    """创建 API Token，返回 token 字符串"""
    name = name or settings.SEED_GPU_TOKEN_NAME
    description = description if description is not None else settings.SEED_GPU_TOKEN_DESCRIPTION
    db_path = db_path or settings.DATABASE_PATH
    token = token_value or settings.SEED_GPU_TOKEN_VALUE or secrets.token_urlsafe(32)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now = int(datetime.now().timestamp() * 1000)
    scopes = json.dumps(["tasks.read", "tasks.update"])

    cursor.execute(
        """
        SELECT token FROM api_tokens WHERE name = ?
    """,
        (name,),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE api_tokens
            SET token = ?, description = ?, scopes = ?, is_active = ?
            WHERE name = ?
        """,
            (token, description, scopes, 1, name),
        )
        status = "updated"
    else:
        cursor.execute(
            """
            INSERT INTO api_tokens (token, name, description, scopes, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (token, name, description, scopes, 1, now),
        )
        status = "created"

    conn.commit()
    conn.close()

    if print_token:
        print(f"✅ API Token 创建完成")
        print(f"   名称: {name}")
        print(f"   Token: {token}")
        print(f"   ⚠️  请妥善保管 Token，不会再次显示！")

    return {
        "status": status,
        "name": name,
        "token": token,
    }


if __name__ == "__main__":
    create_api_token(print_token=True)
