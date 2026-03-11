"""
创建默认管理员账户
"""
import sqlite3
import bcrypt
from datetime import datetime


def create_default_admin(
    db_path: str = "database/disaster.db",
    username: str = "user-707",
    password: str = "srgYJKmvr953yj",
    email: str = "0example@killerbest.com",
):
    """创建默认管理员账户"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = int(datetime.now().timestamp() * 1000)

    cursor.execute(
        """
        INSERT OR IGNORE INTO admin_users
        (username, password_hash, email, full_name, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (username, password_hash, email, "System Administrator", "admin", 1, now),
    )

    conn.commit()
    conn.close()

    print(f"✅ 管理员账户创建完成")
    print(f"   用户名: {username}")
    print(f"   密码: {password}")
    print(f"   ⚠️  请在首次登录后立即修改密码！")


if __name__ == "__main__":
    create_default_admin()
