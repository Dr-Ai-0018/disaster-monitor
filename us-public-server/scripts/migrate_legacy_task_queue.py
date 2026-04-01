"""
将 task_queue 里的旧版 tasks 结构迁移为 Latest Model 当前需要的格式。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.models import Event, TaskQueue, get_session_factory
from utils.task_progress import (
    build_initial_progress_state,
    canonicalize_task_definitions,
    safe_json_loads,
)


RECOVERABLE_ERROR_MARKERS = (
    "Latest Model API 错误 422",
    "task is required",
    "embed it in prompt like [IMG_CAP]",
)


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _is_recoverable_legacy_failure(task: TaskQueue) -> bool:
    error_text = " ".join([
        str(task.failure_reason or ""),
        str(task.last_error_details or ""),
    ])
    return any(marker in error_text for marker in RECOVERABLE_ERROR_MARKERS)


def main() -> int:
    db = get_session_factory()()
    try:
        rows = db.query(TaskQueue).all()
        updated = 0
        reset_to_pending = 0
        now = _now_ms()
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

            # 对仍在队列中的任务，刷新进度结构，避免旧 step_details 与新任务定义不一致。
            if row.status == "pending":
                initial_state = build_initial_progress_state(task_data)
                row.progress_stage = initial_state["progress_stage"]
                row.progress_message = "任务定义已迁移，等待服务重新调度"
                row.progress_percent = initial_state["progress_percent"]
                row.current_step = initial_state["current_step"]
                row.total_steps = initial_state["total_steps"]
                row.step_details = initial_state["step_details"]
                row.updated_at = now

            # 仅恢复由这次旧 schema -> 422 导致的失败任务，不动其他真实失败。
            if row.status == "failed" and _is_recoverable_legacy_failure(row):
                initial_state = build_initial_progress_state(task_data)
                row.status = "pending"
                row.retry_count = 0
                row.pause_requested = 0
                row.paused_at = None
                row.locked_by = None
                row.locked_at = None
                row.locked_until = None
                row.heartbeat = None
                row.completed_at = None
                row.failure_reason = None
                row.last_error_details = None
                row.progress_stage = initial_state["progress_stage"]
                row.progress_message = "旧版任务定义已迁移，等待自动重试"
                row.progress_percent = initial_state["progress_percent"]
                row.current_step = initial_state["current_step"]
                row.total_steps = initial_state["total_steps"]
                row.step_details = initial_state["step_details"]
                row.updated_at = now
                reset_to_pending += 1

                event = db.query(Event).filter(Event.uuid == row.uuid).first()
                if event:
                    event.status = "queued"
                    event.updated_at = now

        db.commit()
        print(f"updated_tasks={updated}")
        print(f"reset_to_pending={reset_to_pending}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
