"""
数据库初始化脚本
"""
import sqlite3
from pathlib import Path


EVENT_COLUMN_MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN pre_window_days INTEGER DEFAULT 7",
    "ALTER TABLE events ADD COLUMN pre_imagery_last_check INTEGER",
    "ALTER TABLE events ADD COLUMN pre_imagery_exhausted INTEGER DEFAULT 0",
    "ALTER TABLE events ADD COLUMN post_window_days INTEGER DEFAULT 7",
    "ALTER TABLE events ADD COLUMN post_imagery_last_check INTEGER",
    "ALTER TABLE events ADD COLUMN post_imagery_open INTEGER DEFAULT 1",
    "ALTER TABLE events ADD COLUMN imagery_check_count INTEGER DEFAULT 0",
]

TASK_QUEUE_COLUMN_MIGRATIONS = [
    "ALTER TABLE task_queue ADD COLUMN last_error_details TEXT",
    "ALTER TABLE task_queue ADD COLUMN progress_stage TEXT DEFAULT 'queued'",
    "ALTER TABLE task_queue ADD COLUMN progress_message TEXT",
    "ALTER TABLE task_queue ADD COLUMN progress_percent INTEGER DEFAULT 0",
    "ALTER TABLE task_queue ADD COLUMN current_step INTEGER DEFAULT 0",
    "ALTER TABLE task_queue ADD COLUMN total_steps INTEGER DEFAULT 0",
    "ALTER TABLE task_queue ADD COLUMN step_details TEXT",
    "ALTER TABLE task_queue ADD COLUMN pause_requested INTEGER DEFAULT 0",
    "ALTER TABLE task_queue ADD COLUMN paused_at INTEGER",
    "ALTER TABLE task_queue ADD COLUMN manual_resume_count INTEGER DEFAULT 0",
]


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _apply_sql_list(cursor: sqlite3.Cursor, sql_list: list[str]):
    for sql in sql_list:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass


def init_database(db_path: str = "database/disaster.db"):
    """初始化数据库，创建所有表"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"schema.sql not found at {schema_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 旧库中的 events 表可能缺少新字段；先补列，避免后续建索引时直接报错。
    if _table_exists(cursor, "events"):
        _apply_sql_list(cursor, EVENT_COLUMN_MIGRATIONS)
    if _table_exists(cursor, "task_queue"):
        _apply_sql_list(cursor, TASK_QUEUE_COLUMN_MIGRATIONS)

    with open(schema_path, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    _apply_sql_list(cursor, EVENT_COLUMN_MIGRATIONS)
    _apply_sql_list(cursor, TASK_QUEUE_COLUMN_MIGRATIONS)

    conn.commit()
    conn.close()

    print(f"Database initialized: {db_path}")


if __name__ == "__main__":
    init_database()
