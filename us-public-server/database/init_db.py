"""
数据库初始化脚本
"""
import sqlite3
from pathlib import Path


def init_database(db_path: str = "database/disaster.db"):
    """初始化数据库，创建所有表"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"schema.sql not found at {schema_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(schema_path, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    conn.commit()
    conn.close()

    print(f"✅ 数据库初始化完成: {db_path}")


if __name__ == "__main__":
    init_database()
