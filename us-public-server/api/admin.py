"""
管理后台 API 路由
"""
import json
import secrets
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session

from models.models import AdminUser, ApiToken, Event, TaskQueue, Product, DailyReport, get_db
from schemas.schemas import (
    SystemStatusResponse, CreateTokenRequest, CreateTokenResponse,
    TokenListItem, MessageResponse,
)
from utils.auth import get_current_admin

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
    "check_gee_tasks",
    "process_pool",
    "generate_daily_report",
    "release_timeout_locks",
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
            elif job_id == "process_pool" or job_id == "check_gee_tasks":
                from core.task_scheduler import job_process_pool
                job_process_pool()
            elif job_id == "release_timeout_locks":
                from core.task_scheduler import job_release_locks
                job_release_locks()
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
