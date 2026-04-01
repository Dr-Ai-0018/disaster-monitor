"""
将 task_queue 里的旧版 tasks 结构迁移为 Latest Model 当前需要的格式。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.models import TaskQueue, get_session_factory
from utils.task_progress import canonicalize_task_definitions, safe_json_loads


def main() -> int:
    db = get_session_factory()()
    try:
        rows = db.query(TaskQueue).all()
        updated = 0
        for row in rows:
            task_data = safe_json_loads(row.task_data, {})
            if not isinstance(task_data, dict):
                continue
            current = task_data.get("tasks") or []
            canonical = canonicalize_task_definitions(current)
            if canonical != current:
                task_data["tasks"] = canonical
                row.task_data = json.dumps(task_data, ensure_ascii=False)
                updated += 1
        db.commit()
        print(f"updated_tasks={updated}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
