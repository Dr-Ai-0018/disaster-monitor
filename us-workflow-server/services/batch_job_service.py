from __future__ import annotations

import json
from threading import Lock, Thread
from typing import Callable

from models.models import WorkflowBatchJob, WorkflowItem, get_session_factory
from services.workflow_service import rollback_to_previous_pool, rollback_to_reaudit_pool

_ACTIVE_JOB_IDS: set[int] = set()
_JOB_LOCK = Lock()
_MAX_STORED_ERRORS = 50


def _now_ms() -> int:
    from datetime import datetime, timezone

    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _load_params(job: WorkflowBatchJob) -> dict:
    if not job.params_json:
        return {}
    try:
        return json.loads(job.params_json)
    except json.JSONDecodeError:
        return {}


def _load_results(job: WorkflowBatchJob) -> dict:
    if not job.result_json:
        return {"errors": []}
    try:
        parsed = json.loads(job.result_json)
    except json.JSONDecodeError:
        return {"errors": []}
    if not isinstance(parsed, dict):
        return {"errors": []}
    parsed.setdefault("errors", [])
    return parsed


def _store_results(job: WorkflowBatchJob, payload: dict) -> None:
    job.result_json = json.dumps(payload, ensure_ascii=False)


def _job_action(job: WorkflowBatchJob) -> Callable:
    if job.action == "rollback_previous":
        return rollback_to_previous_pool
    if job.action == "rollback_reaudit":
        return rollback_to_reaudit_pool
    raise ValueError(f"unsupported job action: {job.action}")


def create_pool_batch_job(db, *, action: str, target_pool: str, created_by: str) -> WorkflowBatchJob:
    if action not in {"rollback_previous", "rollback_reaudit"}:
        raise ValueError(f"unsupported action: {action}")

    uuids = [
        row[0]
        for row in (
            db.query(WorkflowItem.uuid)
            .filter(WorkflowItem.current_pool == target_pool)
            .order_by(WorkflowItem.updated_at.desc(), WorkflowItem.uuid.asc())
            .all()
        )
    ]
    now = _now_ms()
    job = WorkflowBatchJob(
        action=action,
        target_pool=target_pool,
        status="queued",
        progress_total=len(uuids),
        progress_completed=0,
        progress_succeeded=0,
        progress_failed=0,
        progress_message="等待开始",
        cancel_requested=0,
        params_json=json.dumps({"uuids": uuids}, ensure_ascii=False),
        result_json=json.dumps({"errors": []}, ensure_ascii=False),
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_batch_job(db, job_id: int) -> WorkflowBatchJob | None:
    return db.query(WorkflowBatchJob).filter(WorkflowBatchJob.id == job_id).first()


def request_cancel_batch_job(db, job_id: int) -> WorkflowBatchJob | None:
    job = get_batch_job(db, job_id)
    if not job:
        return None

    now = _now_ms()
    if job.status == "queued":
        job.status = "cancelled"
        job.cancel_requested = 1
        job.progress_message = "已取消，任务未开始执行"
        job.finished_at = now
        job.updated_at = now
    elif job.status == "running":
        job.cancel_requested = 1
        job.status = "cancelling"
        job.progress_message = "已请求取消，当前条目完成后停止"
        job.updated_at = now
    db.commit()
    db.refresh(job)
    return job


def dispatch_batch_job(job_id: int) -> None:
    with _JOB_LOCK:
        if job_id in _ACTIVE_JOB_IDS:
            return
        _ACTIVE_JOB_IDS.add(job_id)
    thread = Thread(target=_run_batch_job, args=(job_id,), daemon=True, name=f"workflow-batch-job-{job_id}")
    thread.start()


def _run_batch_job(job_id: int) -> None:
    SessionLocal = get_session_factory()
    try:
        control_db = SessionLocal()
        try:
            job = get_batch_job(control_db, job_id)
            if not job or job.status in {"cancelled", "completed", "failed"}:
                return

            params = _load_params(job)
            uuids = list(params.get("uuids") or [])
            action = _job_action(job)
            now = _now_ms()
            job.status = "running"
            job.started_at = now
            job.updated_at = now
            job.progress_message = "开始执行批量任务"
            control_db.commit()

            for index, uuid in enumerate(uuids, start=1):
                control_db.expire_all()
                job = get_batch_job(control_db, job_id)
                if not job:
                    return
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.progress_message = f"已取消，停止在第 {index} / {len(uuids)} 条之前"
                    job.finished_at = _now_ms()
                    job.updated_at = job.finished_at
                    control_db.commit()
                    return

                item_db = SessionLocal()
                try:
                    result = action(item_db, uuid, operator=f"job:{job.created_by}", commit=True)
                except Exception as exc:
                    item_db.rollback()
                    control_db.expire_all()
                    job = get_batch_job(control_db, job_id)
                    if not job:
                        return
                    results = _load_results(job)
                    if len(results["errors"]) < _MAX_STORED_ERRORS:
                        results["errors"].append({"uuid": uuid, "message": str(exc)})
                    job.progress_completed += 1
                    job.progress_failed += 1
                    job.progress_message = f"执行中：{job.progress_completed}/{job.progress_total}，最近失败 {uuid}"
                    job.updated_at = _now_ms()
                    _store_results(job, results)
                    control_db.commit()
                else:
                    control_db.expire_all()
                    job = get_batch_job(control_db, job_id)
                    if not job:
                        return
                    job.progress_completed += 1
                    job.progress_succeeded += 1
                    job.progress_message = (
                        f"执行中：{job.progress_completed}/{job.progress_total}，最近完成 {result['uuid']}"
                    )
                    job.updated_at = _now_ms()
                    control_db.commit()
                finally:
                    item_db.close()

            control_db.expire_all()
            job = get_batch_job(control_db, job_id)
            if not job:
                return
            now = _now_ms()
            job.status = "completed"
            job.progress_message = (
                f"执行完成：成功 {job.progress_succeeded}，失败 {job.progress_failed}"
            )
            job.finished_at = now
            job.updated_at = now
            control_db.commit()
        finally:
            control_db.close()
    except Exception as exc:
        db = SessionLocal()
        try:
            job = get_batch_job(db, job_id)
            if job:
                now = _now_ms()
                job.status = "failed"
                job.error_message = str(exc)
                job.progress_message = "批量任务异常终止"
                job.finished_at = now
                job.updated_at = now
                db.commit()
        finally:
            db.close()
    finally:
        with _JOB_LOCK:
            _ACTIVE_JOB_IDS.discard(job_id)


def reconcile_batch_jobs_on_startup() -> None:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        now = _now_ms()
        rows = (
            db.query(WorkflowBatchJob)
            .filter(WorkflowBatchJob.status.in_(["queued", "running", "cancelling"]))
            .all()
        )
        for job in rows:
            job.status = "failed"
            job.error_message = "服务重启，批量任务未继续执行，请重新发起"
            job.progress_message = "服务重启后已停止"
            job.finished_at = now
            job.updated_at = now
        if rows:
            db.commit()
    finally:
        db.close()
