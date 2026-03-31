"""
管理后台 API 路由
"""
import csv
import io
import json
import secrets
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.models import AdminUser, ApiToken, Event, TaskQueue, Product, DailyReport, get_db
from schemas.schemas import (
    SystemStatusResponse, CreateTokenRequest, CreateTokenResponse,
    TokenListItem, MessageResponse,
    TaskProgressSummary, TaskProgressDetail,
    TaskProgressListResponse, TaskProgressStatsResponse,
    WorkflowLabQualityRequest, WorkflowLabSummaryRequest,
    WorkflowLabInferenceRequest, WorkflowLabReportRequest,
)
from utils.auth import get_current_admin
from utils.task_progress import (
    build_initial_progress_state,
    safe_json_loads,
    summarize_step_details,
    get_total_steps,
)

router = APIRouter(prefix="/api/admin", tags=["管理后台"])

# ── 脱敏工具 ──────────────────────────────────────────

def _mask(value: str, keep_tail: int = 6) -> str:
    """脱敏：保留末尾 keep_tail 个字符，其余替换为 ****"""
    if not value:
        return ""
    if len(value) <= keep_tail:
        return "****"
    return "****" + value[-keep_tail:]


def _is_masked(value: str) -> bool:
    """判断值是否是脱敏占位符（前端原样回传时不更新）"""
    return isinstance(value, str) and value.startswith("****")


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _task_can_pause(status: str) -> bool:
    return status in {"pending", "running"}


def _task_can_resume(status: str) -> bool:
    return status in {"pause_requested", "paused", "failed"}


def _task_to_progress_payload(
    task: TaskQueue,
    event: Any = None,
    product: Any = None,
) -> Dict[str, Any]:
    task_data = safe_json_loads(task.task_data, {})
    step_details_json = task.step_details
    if not step_details_json:
        step_details_json = build_initial_progress_state(task.task_data)["step_details"]
    step_summary = summarize_step_details(step_details_json)

    return {
        "uuid": task.uuid,
        "event_title": getattr(event, "title", None),
        "event_country": getattr(event, "country", None),
        "event_category": getattr(event, "category_name", None) or getattr(event, "category", None),
        "event_severity": getattr(event, "severity", None),
        "event_status": getattr(event, "status", None),
        "task_status": task.status,
        "progress_stage": task.progress_stage,
        "progress_message": task.progress_message,
        "progress_percent": task.progress_percent or 0,
        "current_step": task.current_step or 0,
        "total_steps": task.total_steps or get_total_steps(task.task_data),
        "task_count": step_summary["task_count"],
        "completed_task_count": step_summary["completed_count"],
        "failed_task_count": step_summary["failed_count"],
        "running_task_label": step_summary["running_label"],
        "retry_count": task.retry_count or 0,
        "max_retries": task.max_retries or 3,
        "manual_resume_count": task.manual_resume_count or 0,
        "pause_requested": bool(task.pause_requested),
        "locked_by": task.locked_by,
        "locked_at": task.locked_at,
        "locked_until": task.locked_until,
        "heartbeat": task.heartbeat,
        "failure_reason": task.failure_reason,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
        "can_pause": _task_can_pause(task.status),
        "can_resume": _task_can_resume(task.status),
        "task_data": task_data,
        "step_details": step_summary["details"],
        "inference_result": safe_json_loads(getattr(product, "inference_result", None), None),
        "last_error_details": task.last_error_details,
    }


def _workflow_lab_snapshot(db: Session, uuid: str) -> Dict[str, Any]:
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    task_payload = _task_to_progress_payload(task, event, product) if task else None

    return {
        "event": {
            "uuid": event.uuid,
            "title": event.title,
            "status": event.status,
            "country": event.country,
            "category": event.category_name or event.category,
            "severity": event.severity,
            "pre_image_path": event.pre_image_path,
            "post_image_path": event.post_image_path,
            "has_pre_image": bool(event.pre_image_path),
            "has_post_image": bool(event.post_image_path),
            "quality_checked": bool(event.quality_checked),
            "quality_pass": bool(event.quality_pass),
            "quality_score": event.quality_score,
            "updated_at": event.updated_at,
        },
        "task": task_payload,
        "product": {
            "exists": bool(product),
            "summary_generated": bool(product.summary_generated) if product else False,
            "updated_at": getattr(product, "updated_at", None),
        },
    }


@router.get("/status", response_model=SystemStatusResponse)
def system_status(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    from config.settings import settings
    import os, time

    # 数据库统计
    total_events = db.query(Event).count()
    tasks_pending = db.query(TaskQueue).filter(TaskQueue.status == "pending").count()
    tasks_running = db.query(TaskQueue).filter(TaskQueue.status == "running").count()
    products_count = db.query(Product).count()

    db_size_mb = 0
    try:
        db_size_mb = round(os.path.getsize(settings.DATABASE_PATH) / 1024 / 1024, 2)
    except Exception:
        pass

    # GEE 状态
    gee_authenticated = False
    gee_running_tasks = 0
    gee_quota_warning = False
    try:
        from core.gee_manager import GeeManager, _gee_initialized
        gee_authenticated = _gee_initialized
        if gee_authenticated:
            gm = GeeManager()
            gee_running_tasks = gm.get_running_task_count()
            gee_quota_warning = gm.is_quota_warning()
    except Exception:
        pass

    # 调度器状态
    scheduler_running = False
    next_jobs = []
    try:
        from core.task_scheduler import scheduler
        scheduler_running = scheduler.running
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            next_jobs.append({
                "job_id": job.id,
                "next_run": int(next_run.timestamp() * 1000) if next_run else None,
            })
    except Exception:
        pass

    return SystemStatusResponse(
        system={
            "status": "healthy",
            "version": "1.0.0",
            "env": settings.APP_ENV,
        },
        database={
            "size_mb": db_size_mb,
            "events_count": total_events,
            "tasks_pending": tasks_pending,
            "tasks_running": tasks_running,
            "products_count": products_count,
        },
        gee={
            "authenticated": gee_authenticated,
            "running_tasks": gee_running_tasks,
            "quota_warning": gee_quota_warning,
        },
        scheduler={
            "running": scheduler_running,
            "next_jobs": next_jobs,
        },
    )


@router.get("/tasks/stats", response_model=TaskProgressStatsResponse)
def task_progress_stats(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    tasks = db.query(TaskQueue).all()
    by_status: Dict[str, int] = {}
    for task in tasks:
        by_status[task.status] = by_status.get(task.status, 0) + 1

    return TaskProgressStatsResponse(
        total=len(tasks),
        by_status=by_status,
        active=sum(by_status.get(key, 0) for key in ["pending", "running"]),
        pause_requested=0,
        paused=0,
        completed=by_status.get("completed", 0),
        failed=by_status.get("failed", 0),
    )


@router.get("/tasks", response_model=TaskProgressListResponse)
def list_task_progress(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query("", description="任务状态筛选"),
    keyword: str = Query("", description="按 UUID / 标题 / 国家搜索"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    query = db.query(TaskQueue).outerjoin(Event, Event.uuid == TaskQueue.uuid)

    if status:
        query = query.filter(TaskQueue.status == status)

    if keyword.strip():
        like_kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                TaskQueue.uuid.like(like_kw),
                Event.title.like(like_kw),
                Event.country.like(like_kw),
            )
        )

    total = query.count()
    pages = max(1, (total + limit - 1) // limit)
    rows = (
        query.order_by(TaskQueue.updated_at.desc(), TaskQueue.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    uuids = [row.uuid for row in rows]
    events = db.query(Event).filter(Event.uuid.in_(uuids)).all() if uuids else []
    products = db.query(Product).filter(Product.uuid.in_(uuids)).all() if uuids else []
    event_map = {item.uuid: item for item in events}
    product_map = {item.uuid: item for item in products}

    return TaskProgressListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        data=[
            TaskProgressSummary(**_task_to_progress_payload(
                row,
                event_map.get(row.uuid),
                product_map.get(row.uuid),
            ))
            for row in rows
        ],
    )


@router.get("/tasks/{uuid}", response_model=TaskProgressDetail)
def get_task_progress(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    event = db.query(Event).filter(Event.uuid == uuid).first()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    return TaskProgressDetail(**_task_to_progress_payload(task, event, product))


@router.get("/workflow-lab/events/{uuid}")
def get_workflow_lab_snapshot(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    return _workflow_lab_snapshot(db, uuid)


@router.post("/workflow-lab/events/{uuid}/quality")
def run_workflow_lab_quality(
    uuid: str,
    req: WorkflowLabQualityRequest,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    if not event.pre_image_path or not event.post_image_path:
        raise HTTPException(status_code=400, detail="AI 质检需要同时具备灾前和灾后影像")

    from core.quality_assessor import QualityAssessor

    qa = QualityAssessor()
    result = qa.assess_pair(event.pre_image_path, event.post_image_path)

    if req.persist:
        now = _now_ms()
        event.quality_score = result.get("score", 0)
        event.quality_assessment = json.dumps(result, ensure_ascii=False)
        event.quality_checked = 1
        event.quality_pass = 1 if result.get("pass") else 0
        event.quality_check_time = now
        if result.get("pass"):
            event.status = "checked"
        event.updated_at = now
        db.commit()

    return {
        "message": "AI 质检已完成",
        "persisted": req.persist,
        "result": result,
        "snapshot": _workflow_lab_snapshot(db, uuid),
    }


@router.post("/workflow-lab/events/{uuid}/inference")
def run_workflow_lab_inference(
    uuid: str,
    req: WorkflowLabInferenceRequest,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if task and task.status in {"running", "pause_requested"}:
        raise HTTPException(status_code=409, detail="任务正在执行中，请稍后再试")

    from core.pool_manager import PoolManager

    pm = PoolManager(db)
    selected = req.image_type or None
    now = _now_ms()

    if not task:
        if event.status != "checked":
            raise HTTPException(status_code=400, detail=f"当前事件状态为 {event.status}，无法直接创建推理任务")
        pm.enqueue_checked_events(limit=1, target_uuid=uuid, preferred_image_type=selected)
        task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    elif req.reset_task:
        task_data = pm._build_task_data(event, preferred_image_type=selected)
        initial_state = build_initial_progress_state(task_data)
        task.task_data = json.dumps(task_data, ensure_ascii=False)
        task.status = "pending"
        task.pause_requested = 0
        task.paused_at = None
        task.locked_by = None
        task.locked_at = None
        task.locked_until = None
        task.heartbeat = None
        task.completed_at = None
        task.failure_reason = None
        task.last_error_details = None
        task.progress_stage = initial_state["progress_stage"]
        task.progress_message = "工作流测试台已重新排队该任务"
        task.progress_percent = initial_state["progress_percent"]
        task.current_step = initial_state["current_step"]
        task.total_steps = initial_state["total_steps"]
        task.step_details = initial_state["step_details"]
        task.updated_at = now
        event.status = "queued"
        event.updated_at = now
        db.commit()
    elif selected:
        task_data = safe_json_loads(task.task_data, {}) or {}
        rebuilt = pm._build_task_data(event, preferred_image_type=selected)
        task_data["image_path"] = rebuilt.get("image_path")
        task_data["image_kind"] = rebuilt.get("image_kind")
        task_data["selected_image_type"] = selected
        task.task_data = json.dumps(task_data, ensure_ascii=False)
        task.updated_at = now
        db.commit()

    processed = pm.process_pending_inference_tasks(limit=1, target_uuid=uuid)

    return {
        "message": "指定事件推理测试已触发",
        "processed": processed,
        "snapshot": _workflow_lab_snapshot(db, uuid),
    }


@router.post("/workflow-lab/events/{uuid}/summary")
def run_workflow_lab_summary(
    uuid: str,
    req: WorkflowLabSummaryRequest,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.uuid == uuid).first()
    if not product:
        raise HTTPException(status_code=404, detail="成品不存在，请先完成推理")

    from core.report_generator import ReportGenerator

    rg = ReportGenerator()
    summary = rg.generate_event_summary(product)
    if not summary:
        raise HTTPException(status_code=500, detail="单事件摘要生成失败")

    if req.persist:
        product.summary = summary
        product.summary_generated = 1
        product.summary_generated_at = _now_ms()
        product.updated_at = _now_ms()
        db.commit()

    return {
        "message": "单事件摘要测试已完成",
        "persisted": req.persist,
        "summary": summary,
        "snapshot": _workflow_lab_snapshot(db, uuid),
    }


@router.post("/workflow-lab/reports/generate")
def run_workflow_lab_report(
    req: WorkflowLabReportRequest,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    from core.report_generator import ReportGenerator

    rg = ReportGenerator()
    report = rg.generate_daily_report(db, req.date)
    if not report:
        raise HTTPException(status_code=404, detail=f"日期 {req.date} 无可生成日报的数据")

    return {
        "message": "日报测试已完成",
        "report": {
            "date": report.report_date,
            "title": report.report_title,
            "event_count": report.event_count,
            "published": bool(report.published),
            "generated_at": report.generated_at,
        },
    }


@router.post("/tasks/{uuid}/pause", response_model=MessageResponse)
def pause_task_progress(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    event = db.query(Event).filter(Event.uuid == uuid).first()
    now = _now_ms()

    if task.status == "pending":
        task.status = "paused"
        task.pause_requested = 0
        task.paused_at = now
        task.locked_by = None
        task.locked_at = None
        task.locked_until = None
        task.heartbeat = None
        task.progress_stage = "paused"
        task.progress_message = "任务已手动暂停，等待继续"
        task.updated_at = now
        if event:
            event.status = "queued"
            event.updated_at = now
        db.commit()
        return MessageResponse(message="任务已暂停")

    if task.status in {"locked", "running"}:
        task.status = "pause_requested"
        task.pause_requested = 1
        task.progress_stage = "pause_requested"
        task.progress_message = "已发送暂停请求，将在当前子步骤完成后停止"
        task.updated_at = now
        db.commit()
        return MessageResponse(message="暂停请求已发送")

    if task.status == "pause_requested":
        return MessageResponse(message="暂停请求已在处理中")

    if task.status == "paused":
        return MessageResponse(message="任务已处于暂停状态")

    raise HTTPException(status_code=400, detail=f"当前状态 {task.status} 不支持暂停")


@router.post("/tasks/{uuid}/resume", response_model=MessageResponse)
def resume_task_progress(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status not in {"pause_requested", "paused", "failed"}:
        raise HTTPException(status_code=400, detail=f"当前状态 {task.status} 不支持继续")

    previous_status = task.status
    event = db.query(Event).filter(Event.uuid == uuid).first()
    now = _now_ms()

    if previous_status == "pause_requested":
        lock_is_alive = bool(task.locked_by and task.locked_until and task.locked_until > now)

        if lock_is_alive:
            task.status = "running"
            task.pause_requested = 0
            task.paused_at = None
            task.progress_stage = "claimed" if task.progress_stage == "pause_requested" else task.progress_stage
            task.progress_message = "已取消暂停请求，任务继续执行"
            task.updated_at = now
            db.commit()
            return MessageResponse(message="已取消暂停请求，任务继续执行")

        previous_status = "paused"

    initial_state = build_initial_progress_state(task.task_data)

    task.status = "pending"
    task.pause_requested = 0
    task.paused_at = None
    task.locked_by = None
    task.locked_at = None
    task.locked_until = None
    task.heartbeat = None
    task.completed_at = None
    task.failure_reason = None
    task.last_error_details = None
    task.progress_stage = initial_state["progress_stage"]
    task.progress_message = "已手动继续，等待 Worker 重新执行"
    task.progress_percent = initial_state["progress_percent"]
    task.current_step = initial_state["current_step"]
    task.total_steps = initial_state["total_steps"]
    task.step_details = initial_state["step_details"]
    task.manual_resume_count = (task.manual_resume_count or 0) + 1
    if previous_status == "failed":
        task.retry_count = 0
    else:
        task.retry_count = task.retry_count or 0
    task.updated_at = now

    if event:
        event.status = "queued"
        event.updated_at = now

    db.commit()
    return MessageResponse(message="任务已重新排队，等待 Worker 继续")


# ── API Token 管理 ────────────────────────────────────

@router.get("/tokens", response_model=List[TokenListItem])
def list_tokens(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return [
        TokenListItem(
            token_ref=sha256(t.token.encode("utf-8")).hexdigest()[:16],
            token=t.token[:8] + "..." + t.token[-4:],  # 脱敏显示
            name=t.name,
            description=t.description,
            is_active=bool(t.is_active),
            usage_count=t.usage_count or 0,
            last_used=t.last_used,
            created_at=t.created_at,
        )
        for t in tokens
    ]


@router.post("/tokens", response_model=CreateTokenResponse)
def create_token(
    req: CreateTokenRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Token 名称不能为空")
    existing = db.query(ApiToken).filter(ApiToken.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Token 名称 '{name}' 已存在")

    token_str = secrets.token_urlsafe(32)
    now = _now_ms()
    token = ApiToken(
        token=token_str,
        name=name,
        description=req.description,
        scopes=json.dumps(req.scopes),
        is_active=1,
        created_at=now,
        created_by=current_user.id,
    )
    db.add(token)
    db.commit()
    return CreateTokenResponse(token=token_str, name=name, created_at=now)


@router.delete("/tokens/{token_name}", response_model=MessageResponse)
def disable_token(
    token_name: str,
    created_at: int = Query(..., description="Token 创建时间，用于精确定位记录"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    token = db.query(ApiToken).filter(
        ApiToken.name == token_name,
        ApiToken.created_at == created_at,
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token 不存在")
    if not token.is_active:
        return MessageResponse(message=f"Token '{token_name}' 已禁用")
    token.is_active = 0
    db.commit()
    return MessageResponse(message=f"Token '{token_name}' 已禁用")


# ── 系统配置读写 ───────────────────────────────────────

# 前端字段名 → .env key 映射（is_secret=True 时返回脱敏值）
_ENV_FIELD_MAP: Dict[str, tuple] = {
    # (env_key, is_secret)
    "openai_api_key":          ("OPENAI_API_KEY",          True),
    "openai_base_url":         ("OPENAI_BASE_URL",         False),
    "openai_model":            ("OPENAI_MODEL",            False),
    "latest_model_endpoint":   ("LATEST_MODEL_ENDPOINT",   False),
    "latest_model_api_key":    ("LATEST_MODEL_API_KEY",    True),
    "gemini_api_key":          ("GEMINI_API_KEY",          True),
    "gemini_base_url":         ("GEMINI_BASE_URL",         False),
    "gemini_flash_model":      ("GEMINI_FLASH_MODEL",      False),
    "gemini_pro_model":        ("GEMINI_PRO_MODEL",        False),
    "session_edis_web":        ("SESSION_EDIS_WEB",        True),
    "arr_affinity":            ("ARR_AFFINITY",            True),
    "arr_affinity_same_site":  ("ARR_AFFINITY_SAME_SITE",  True),
    "ga":                      ("_GA",                     False),
    "gads":                    ("__GADS",                  False),
    "gpi":                     ("__GPI",                   False),
    "eoi":                     ("__EOI",                   False),
    "ga_kh":                   ("_GA_KHD7YP5VHW",         False),
    "gee_project_id":          ("GEE_PROJECT_ID",          False),
    "gee_service_account_email": ("GEE_SERVICE_ACCOUNT_EMAIL", False),
    "request_timeout":         ("REQUEST_TIMEOUT",         False),
    "request_delay":           ("REQUEST_DELAY",           False),
    "cors_origins":            ("CORS_ORIGINS",            False),
    "log_level":               ("LOG_LEVEL",               False),
}

# 前端字段名 → config.json 路径映射
_JSON_FIELD_MAP: Dict[str, tuple] = {
    # (path_list, python_type)
    "gee_cloud_threshold":          (["gee", "cloud_threshold"],                    int),
    "gee_time_before":              (["gee", "time_window_days_before"],             int),
    "gee_time_after":               (["gee", "time_window_days_after"],              int),
    "gee_scale":                    (["gee", "scale"],                               int),
    "gee_max_concurrent":           (["gee", "max_concurrent_tasks"],                int),
    "quality_enabled":              (["quality_assessment", "enabled"],              bool),
    "quality_cloud_threshold":      (["quality_assessment", "cloud_coverage_threshold"], int),
    "quality_pass_score":           (["quality_assessment", "pass_score_threshold"], int),
    "quality_fail_open":            (["quality_assessment", "fail_open"],            bool),
    "quality_max_retries":          (["quality_assessment", "max_retries"],          int),
    "sched_fetch_enabled":          (["scheduler", "fetch_rsoe_data", "enabled"],    bool),
    "sched_pool_enabled":           (["scheduler", "process_pool", "enabled"],       bool),
    "sched_inference_enabled":      (["scheduler", "process_inference_queue", "enabled"], bool),
    "sched_recheck_enabled":        (["scheduler", "recheck_imagery", "enabled"],    bool),
    "sched_report_enabled":         (["scheduler", "generate_daily_report", "enabled"], bool),
    "report_top_events":            (["report_generation", "top_events_count"],      int),
    "report_max_summary_len":       (["report_generation", "max_summary_length"],    int),
    "rsoe_request_timeout":         (["rsoe", "request_timeout"],                    int),
    "rsoe_request_delay":           (["rsoe", "request_delay"],                      float),
    "rsoe_max_retries":             (["rsoe", "max_retries"],                        int),
}


def _get_nested(obj: dict, path: list, default=None):
    for key in path:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return default
    return obj if obj is not None else default


def _cast(value: Any, typ: type) -> Any:
    if typ == bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")
    try:
        return typ(value)
    except (ValueError, TypeError):
        return value


@router.get("/settings")
def get_settings(_: AdminUser = Depends(get_current_admin)):
    """读取所有可配置项（敏感字段脱敏返回）"""
    from config.settings import settings
    from utils.config_manager import read_config_json

    cfg = read_config_json()

    result: Dict[str, Any] = {}

    # .env 字段
    for field, (env_key, is_secret) in _ENV_FIELD_MAP.items():
        raw = getattr(settings, env_key, "") or ""
        result[field] = _mask(raw) if is_secret and raw else raw

    # config.json 字段
    for field, (path, _) in _JSON_FIELD_MAP.items():
        result[field] = _get_nested(cfg, path)

    return result


@router.put("/settings")
def update_settings(
    updates: Dict[str, Any],
    _: AdminUser = Depends(get_current_admin),
):
    """更新配置项：写入 .env / config.json 并热更新内存 settings"""
    from utils.config_manager import (
        write_env_keys, read_config_json, write_config_json,
        set_nested, apply_to_settings,
    )

    env_updates: Dict[str, str] = {}
    cfg = None  # 懒加载 config.json

    for field, value in updates.items():
        # .env 字段
        if field in _ENV_FIELD_MAP:
            env_key, is_secret = _ENV_FIELD_MAP[field]
            if is_secret and _is_masked(str(value)):
                continue  # 前端回传脱敏占位符，不更新
            env_updates[env_key] = str(value)

        # config.json 字段
        elif field in _JSON_FIELD_MAP:
            if cfg is None:
                cfg = read_config_json()
            path, typ = _JSON_FIELD_MAP[field]
            set_nested(cfg, path, _cast(value, typ))

    errors = []
    if env_updates:
        if not write_env_keys(env_updates):
            errors.append(".env 写入失败")
        else:
            apply_to_settings(env_updates)

    if cfg is not None:
        if not write_config_json(cfg):
            errors.append("config.json 写入失败")

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return {"message": f"已更新 {len(updates)} 项配置", "updated": list(updates.keys())}


# ── 手动触发定时任务 ───────────────────────────────────

VALID_JOBS = {
    "fetch_rsoe_data",
    "process_pool",
    "process_inference_queue",
    "generate_daily_report",
    "recheck_imagery",
}


@router.post("/jobs/{job_id}/trigger", response_model=MessageResponse)
def trigger_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    if job_id not in VALID_JOBS:
        raise HTTPException(status_code=400, detail=f"未知任务: {job_id}")

    def _run():
        from models.models import get_session_factory
        s = get_session_factory()()
        try:
            if job_id == "fetch_rsoe_data":
                from core.task_scheduler import job_fetch_rsoe
                job_fetch_rsoe()
            elif job_id == "process_pool":
                from core.task_scheduler import job_process_pool
                job_process_pool()
            elif job_id == "process_inference_queue":
                from core.task_scheduler import job_process_inference_queue
                job_process_inference_queue()
            elif job_id == "generate_daily_report":
                from core.task_scheduler import job_generate_report
                job_generate_report()
            elif job_id == "recheck_imagery":
                from core.task_scheduler import job_recheck_imagery
                job_recheck_imagery()
        finally:
            s.close()

    background_tasks.add_task(_run)
    return MessageResponse(message=f"任务 '{job_id}' 已触发")


@router.post("/gee/reinitialize", response_model=MessageResponse)
def reinitialize_gee(
    background_tasks: BackgroundTasks,
    _: AdminUser = Depends(get_current_admin),
):
    """手动重新初始化 GEE（后台执行，立即返回）"""
    def _run():
        import core.gee_manager as gm
        gm._gee_initialized = False
        from core.gee_manager import initialize_gee
        initialize_gee()

    background_tasks.add_task(_run)
    return MessageResponse(message="GEE 重新初始化已在后台启动，请稍后刷新系统状态")


@router.get("/export/events")
def export_events_csv(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    from models.models import GeeTask
    from api.events import _build_imagery_count_map

    events = db.query(Event).order_by(Event.event_date.desc()).all()
    count_map = _build_imagery_count_map(db, [e.uuid for e in events])

    headers = [
        "uuid", "event_id", "sub_id", "title", "category_name", "country", "severity",
        "event_date", "status", "pre_image_downloaded", "post_image_downloaded",
        "pre_imagery_count", "post_imagery_count", "quality_pass", "created_at",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for e in events:
        counts = count_map.get(e.uuid, {})
        pre_c = counts.get("pre", 1 if e.pre_image_downloaded else 0)
        post_c = counts.get("post", 1 if e.post_image_downloaded else 0)
        w.writerow([
            e.uuid, e.event_id, e.sub_id, e.title, e.category_name, e.country, e.severity,
            datetime.fromtimestamp(e.event_date / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if e.event_date else "",
            e.status,
            int(bool(e.pre_image_downloaded)), int(bool(e.post_image_downloaded)),
            pre_c, post_c, int(bool(e.quality_pass)),
            datetime.fromtimestamp(e.created_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if e.created_at else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=events.csv"},
    )


@router.get("/export/gee-tasks")
def export_gee_tasks_csv(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    from models.models import GeeTask

    rows = (
        db.query(GeeTask, Event.title)
        .outerjoin(Event, Event.uuid == GeeTask.uuid)
        .order_by(GeeTask.created_at.desc())
        .all()
    )

    headers = [
        "id", "event_uuid", "event_title", "task_type", "status",
        "start_date", "end_date", "image_date", "image_source",
        "failure_reason", "retry_count", "created_at", "completed_at",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for t, title in rows:
        def ts(ms):
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ms else ""
        w.writerow([
            t.id, t.uuid, title or "", t.task_type, t.status,
            t.start_date, t.end_date,
            datetime.fromtimestamp(t.image_date / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if t.image_date else "",
            t.image_source, t.failure_reason, t.retry_count,
            ts(t.created_at), ts(t.completed_at),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=gee_tasks.csv"},
    )
