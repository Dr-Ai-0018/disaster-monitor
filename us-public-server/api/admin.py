"""
管理后台 API 路由
"""
import json
import secrets
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from models.models import AdminUser, ApiToken, Event, TaskQueue, Product, DailyReport, get_db
from schemas.schemas import (
    SystemStatusResponse, CreateTokenRequest, CreateTokenResponse,
    TokenListItem, MessageResponse,
)
from utils.auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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
    tasks_locked = db.query(TaskQueue).filter(TaskQueue.status == "locked").count()
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
            "tasks_locked": tasks_locked,
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


# ── API Token 管理 ────────────────────────────────────

@router.get("/tokens", response_model=List[TokenListItem])
def list_tokens(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return [
        TokenListItem(
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
    token_str = secrets.token_urlsafe(32)
    now = _now_ms()
    token = ApiToken(
        token=token_str,
        name=req.name,
        description=req.description,
        scopes=json.dumps(req.scopes),
        is_active=1,
        created_at=now,
        created_by=current_user.id,
    )
    db.add(token)
    db.commit()
    return CreateTokenResponse(token=token_str, name=req.name, created_at=now)


@router.delete("/tokens/{token_name}", response_model=MessageResponse)
def disable_token(
    token_name: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    token = db.query(ApiToken).filter(ApiToken.name == token_name).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token 不存在")
    token.is_active = 0
    db.commit()
    return MessageResponse(message=f"Token '{token_name}' 已禁用")


# ── 手动触发定时任务 ───────────────────────────────────

VALID_JOBS = {
    "fetch_rsoe_data",
    "check_gee_tasks",
    "process_pool",
    "generate_daily_report",
    "release_timeout_locks",
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
            elif job_id == "release_timeout_locks":
                from core.task_scheduler import job_release_locks
                job_release_locks()
            elif job_id == "generate_daily_report":
                from datetime import date
                from core.task_scheduler import job_generate_report
                job_generate_report()
        finally:
            s.close()

    background_tasks.add_task(_run)
    return MessageResponse(message=f"任务 '{job_id}' 已触发")
