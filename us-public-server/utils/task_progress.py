"""
任务进度共享工具
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def safe_json_loads(raw: Any, default: Any):
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def normalize_task_definitions(task_data_raw: Any) -> List[Dict[str, Any]]:
    task_data = safe_json_loads(task_data_raw, {})
    tasks = task_data.get("tasks") if isinstance(task_data, dict) else []
    if not isinstance(tasks, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue
        task_id = task.get("task_id") or index
        task_type = str(task.get("task") or task.get("type") or "UNKNOWN")
        prompt = str(task.get("prompt") or "").strip()
        label = prompt or task_type
        normalized.append({
            "task_id": task_id,
            "type": task_type,
            "prompt": prompt,
            "label": label,
        })
    return normalized


def canonicalize_task_definitions(tasks_raw: Any) -> List[Dict[str, Any]]:
    tasks = tasks_raw if isinstance(tasks_raw, list) else []
    canonical: List[Dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue
        task_id = task.get("task_id") or index
        task_type = str(task.get("task") or task.get("type") or "UNKNOWN").strip().upper() or "UNKNOWN"
        prompt = str(task.get("prompt") or "").strip()
        tagged_prompt = prompt if prompt.startswith(f"[{task_type}]") else f"[{task_type}] {prompt}".strip()
        canonical.append({
            "task_id": task_id,
            "task": task_type,
            "type": task_type,
            "prompt": tagged_prompt,
        })
    return canonical


def get_total_steps(task_data_raw: Any) -> int:
    # 3 个主阶段 + N 个推理子任务。
    return max(len(normalize_task_definitions(task_data_raw)) + 3, 4)


def build_step_details(task_data_raw: Any) -> Dict[str, Any]:
    return {
        "pipeline": [
            {"key": "prepare_image", "label": "准备影像", "status": "pending"},
            {"key": "submit_remote_job", "label": "提交远程推理任务", "status": "pending"},
            {"key": "poll_remote_result", "label": "轮询远程推理结果", "status": "pending"},
            {"key": "save_product", "label": "写入成品池", "status": "pending"},
        ],
        "inference_tasks": [
            {
                "task_id": item["task_id"],
                "type": item["type"],
                "label": item["label"],
                "status": "pending",
            }
            for item in normalize_task_definitions(task_data_raw)
        ],
    }


def build_initial_progress_state(task_data_raw: Any) -> Dict[str, Any]:
    total_steps = get_total_steps(task_data_raw)
    return {
        "progress_stage": "queued",
        "progress_message": "等待服务内部调度推理任务",
        "progress_percent": 0,
        "current_step": 0,
        "total_steps": total_steps,
        "step_details": json.dumps(
            build_step_details(task_data_raw),
            ensure_ascii=False,
        ),
    }


def summarize_step_details(step_details_raw: Any) -> Dict[str, Any]:
    details = safe_json_loads(step_details_raw, {}) or {}
    inference_tasks = details.get("inference_tasks") or []

    completed = 0
    failed = 0
    running_label: Optional[str] = None

    for item in inference_tasks:
        status = str(item.get("status") or "").lower()
        if status in {"completed", "success", "skipped"}:
            completed += 1
        elif status == "failed":
            failed += 1
        elif status == "running" and running_label is None:
            running_label = item.get("label") or item.get("type")

    return {
        "details": details,
        "completed_count": completed,
        "failed_count": failed,
        "running_label": running_label,
        "task_count": len(inference_tasks),
    }
