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

    # 增量迁移：为已存在的 events 表补充动态影像追踪字段
    _MIGRATIONS = [
        "ALTER TABLE events ADD COLUMN pre_window_days INTEGER DEFAULT 7",
        "ALTER TABLE events ADD COLUMN pre_imagery_last_check INTEGER",
        "ALTER TABLE events ADD COLUMN pre_imagery_exhausted INTEGER DEFAULT 0",
        "ALTER TABLE events ADD COLUMN post_window_days INTEGER DEFAULT 7",
        "ALTER TABLE events ADD COLUMN post_imagery_last_check INTEGER",
        "ALTER TABLE events ADD COLUMN post_imagery_open INTEGER DEFAULT 1",
        "ALTER TABLE events ADD COLUMN imagery_check_count INTEGER DEFAULT 0",
    ]
    for sql in _MIGRATIONS:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass  # 字段已存在，忽略

    conn.commit()
    conn.close()

    print(f"✅ 数据库初始化完成: {db_path}")


if __name__ == "__main__":
    init_database()
