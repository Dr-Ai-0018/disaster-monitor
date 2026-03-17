"""
创建默认管理员账户
"""
import sqlite3
import bcrypt
from datetime import datetime
from typing import Dict

from config.settings import settings


def create_default_admin(
    db_path: str = None,
    username: str = None,
    password: str = None,
    email: str = None,
    print_credentials: bool = False,
) -> Dict[str, str]:
    """创建默认管理员账户"""
    db_path = db_path or settings.DATABASE_PATH
    username = username or settings.SEED_ADMIN_USERNAME
    password = password or settings.SEED_ADMIN_PASSWORD
    email = email or settings.SEED_ADMIN_EMAIL

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = int(datetime.now().timestamp() * 1000)

    cursor.execute(
        """
        SELECT id FROM admin_users WHERE username = ?
    """,
        (username,),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE admin_users
            SET password_hash = ?, email = ?, full_name = ?, role = ?, is_active = ?
            WHERE username = ?
        """,
            (password_hash, email, settings.SEED_ADMIN_FULL_NAME, "admin", 1, username),
        )
        status = "updated"
    else:
        cursor.execute(
            """
            INSERT INTO admin_users
            (username, password_hash, email, full_name, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (username, password_hash, email, settings.SEED_ADMIN_FULL_NAME, "admin", 1, now),
        )
        status = "created"

    conn.commit()
    conn.close()

    if print_credentials:
        print(f"✅ 管理员账户创建完成")
        print(f"   用户名: {username}")
        print(f"   密码: {password}")
        print(f"   ⚠️  请在首次登录后立即修改密码！")

    return {
        "status": status,
        "username": username,
        "email": email,
    }


if __name__ == "__main__":
    create_default_admin(print_credentials=True)
