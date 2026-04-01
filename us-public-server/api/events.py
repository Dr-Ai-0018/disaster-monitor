"""
事件管理 API 路由
"""
import json
import math
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.models import AdminUser, Event, GeeTask, TaskQueue, get_db
from schemas.schemas import (
    EventListResponse, EventSummary, EventDetail, EventStatsResponse, MessageResponse, ProcessEventRequest
)
from utils.auth import get_current_admin
from utils.task_progress import build_initial_progress_state, safe_json_loads

router = APIRouter(prefix="/api/events", tags=["事件管理"])


def _build_imagery_count_map(db: Session, uuids: List[str]) -> dict[str, dict[str, int]]:
    if not uuids:
        return {}

    rows = (
        db.query(GeeTask.uuid, GeeTask.task_type, func.count(GeeTask.id))
        .filter(
            GeeTask.uuid.in_(uuids),
            GeeTask.status == "COMPLETED",
            GeeTask.task_type.in_(["pre_disaster", "post_disaster"]),
        )
        .group_by(GeeTask.uuid, GeeTask.task_type)
        .all()
    )

    result: dict[str, dict[str, int]] = {}
    for uuid, task_type, count in rows:
        if uuid not in result:
            result[uuid] = {"pre": 0, "post": 0}
        if task_type == "pre_disaster":
            result[uuid]["pre"] = int(count or 0)
        elif task_type == "post_disaster":
            result[uuid]["post"] = int(count or 0)
    return result


def _event_to_summary(e: Event, imagery_counts: Optional[dict[str, int]] = None) -> EventSummary:
    imagery_counts = imagery_counts or {}
    pre_count = int(imagery_counts.get("pre", 0) or 0)
    post_count = int(imagery_counts.get("post", 0) or 0)
    # 兼容旧数据: 事件表已标记下载成功，但 gee_tasks 没有历史记录
    if bool(e.pre_image_downloaded) and pre_count == 0:
        pre_count = 1
    if bool(e.post_image_downloaded) and post_count == 0:
        post_count = 1

    return EventSummary(
        uuid=e.uuid,
        event_id=e.event_id,
        sub_id=e.sub_id or 0,
        title=e.title,
        category=e.category,
        category_name=e.category_name,
        country=e.country,
        continent=e.continent,
        severity=e.severity,
        longitude=e.longitude,
        latitude=e.latitude,
        event_date=e.event_date,
        last_update=e.last_update,
        status=e.status,
        pre_image_downloaded=bool(e.pre_image_downloaded),
        post_image_downloaded=bool(e.post_image_downloaded),
        quality_pass=bool(e.quality_pass),
        created_at=e.created_at,
        updated_at=e.updated_at,
        pre_window_days=getattr(e, "pre_window_days", 7),
        post_window_days=getattr(e, "post_window_days", 7),
        post_imagery_open=bool(getattr(e, "post_imagery_open", 1)),
        imagery_check_count=getattr(e, "imagery_check_count", 0) or 0,
        pre_imagery_count=pre_count,
        post_imagery_count=post_count,
        has_pre_image=bool(e.pre_image_path),
        has_post_image=bool(e.post_image_path),
        detail_fetch_status=getattr(e, "detail_fetch_status", None),
        detail_fetch_attempts=getattr(e, "detail_fetch_attempts", 0) or 0,
        detail_fetch_http_status=getattr(e, "detail_fetch_http_status", None),
    )


def _event_to_detail(e: Event, imagery_counts: Optional[dict[str, int]] = None) -> EventDetail:
    imagery_counts = imagery_counts or {}
    pre_count = int(imagery_counts.get("pre", 0) or 0)
    post_count = int(imagery_counts.get("post", 0) or 0)
    if bool(e.pre_image_downloaded) and pre_count == 0:
        pre_count = 1
    if bool(e.post_image_downloaded) and post_count == 0:
        post_count = 1

    qa = None
    if e.quality_assessment:
        try:
            qa = json.loads(e.quality_assessment)
        except Exception:
            qa = e.quality_assessment
    dj = None
    if e.details_json:
        try:
            dj = json.loads(e.details_json)
        except Exception:
            dj = e.details_json

    return EventDetail(
        uuid=e.uuid,
        event_id=e.event_id,
        sub_id=e.sub_id or 0,
        title=e.title,
        category=e.category,
        category_name=e.category_name,
        country=e.country,
        continent=e.continent,
        severity=e.severity,
        longitude=e.longitude,
        latitude=e.latitude,
        address=e.address,
        event_date=e.event_date,
        last_update=e.last_update,
        details_json=dj,
        source_url=e.source_url,
        status=e.status,
        pre_image_downloaded=bool(e.pre_image_downloaded),
        pre_image_path=e.pre_image_path,
        pre_image_date=e.pre_image_date,
        pre_image_source=e.pre_image_source,
        post_image_downloaded=bool(e.post_image_downloaded),
        post_image_path=e.post_image_path,
        post_image_date=e.post_image_date,
        post_image_source=e.post_image_source,
        quality_score=e.quality_score,
        quality_assessment=qa,
        quality_checked=bool(e.quality_checked),
        quality_check_time=e.quality_check_time,
        quality_pass=bool(e.quality_pass),
        created_at=e.created_at,
        updated_at=e.updated_at,
        pre_window_days=getattr(e, "pre_window_days", 7),
        post_window_days=getattr(e, "post_window_days", 7),
        post_imagery_open=bool(getattr(e, "post_imagery_open", 1)),
        imagery_check_count=getattr(e, "imagery_check_count", 0) or 0,
        pre_imagery_exhausted=bool(getattr(e, "pre_imagery_exhausted", 0)),
        pre_imagery_last_check=getattr(e, "pre_imagery_last_check", None),
        post_imagery_last_check=getattr(e, "post_imagery_last_check", None),
        pre_imagery_count=pre_count,
        post_imagery_count=post_count,
        has_pre_image=bool(e.pre_image_path),
        has_post_image=bool(e.post_image_path),
        detail_fetch_status=getattr(e, "detail_fetch_status", None),
        detail_fetch_attempts=getattr(e, "detail_fetch_attempts", 0) or 0,
        detail_fetch_http_status=getattr(e, "detail_fetch_http_status", None),
        detail_fetch_last_attempt=getattr(e, "detail_fetch_last_attempt", None),
        detail_fetch_error=getattr(e, "detail_fetch_error", None),
        detail_fetch_completed_at=getattr(e, "detail_fetch_completed_at", None),
    )


@router.get("", response_model=EventListResponse)
def list_events(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[int] = None,
    end_date: Optional[int] = None,
    imagery_open: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    q = db.query(Event)
    if status:
        q = q.filter(Event.status == status)
    if category:
        q = q.filter(Event.category == category.upper())
    if country:
        q = q.filter(Event.country.ilike(f"%{country}%"))
    if severity:
        q = q.filter(Event.severity == severity.lower())
    if start_date:
        q = q.filter(Event.event_date >= start_date)
    if end_date:
        q = q.filter(Event.event_date <= end_date)
    if imagery_open is not None:
        q = q.filter(Event.post_imagery_open == (1 if imagery_open else 0))

    total = q.count()
    events = q.order_by(Event.event_date.desc()).offset((page - 1) * limit).limit(limit).all()

    imagery_count_map = _build_imagery_count_map(db, [e.uuid for e in events])

    return EventListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total else 0,
        data=[_event_to_summary(e, imagery_count_map.get(e.uuid)) for e in events],
    )


@router.get("/stats", response_model=EventStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    all_events = db.query(Event).all()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    day_ms = 86400 * 1000

    by_status: dict = {}
    by_category: dict = {}
    by_severity: dict = {}
    recent_24h = 0

    both_ready = 0
    post_pending = 0
    pre_only = 0
    exhausted = 0

    for e in all_events:
        by_status[e.status] = by_status.get(e.status, 0) + 1
        if e.category:
            by_category[e.category] = by_category.get(e.category, 0) + 1
        if e.severity:
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        if e.created_at and (now_ms - e.created_at) <= day_ms:
            recent_24h += 1

        pre_ok = bool(e.pre_image_downloaded)
        post_ok = bool(e.post_image_downloaded)
        if pre_ok and post_ok:
            both_ready += 1
        elif pre_ok and not post_ok and getattr(e, "post_imagery_open", 1):
            post_pending += 1
        elif pre_ok and not post_ok:
            pre_only += 1
        elif not pre_ok and getattr(e, "pre_imagery_exhausted", 0) and \
                not getattr(e, "post_imagery_open", 1):
            exhausted += 1

    return EventStatsResponse(
        total_events=len(all_events),
        by_status=by_status,
        by_category=by_category,
        by_severity=by_severity,
        recent_24h=recent_24h,
        by_imagery_status={
            "both_ready": both_ready,
            "post_pending": post_pending,
            "pre_only": pre_only,
            "exhausted": exhausted,
        },
    )


@router.get("/{uuid}/gee-tasks")
def get_event_gee_tasks(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    tasks = (
        db.query(GeeTask)
        .filter(GeeTask.uuid == uuid)
        .order_by(GeeTask.created_at.desc())
        .all()
    )
    return {
        "uuid": uuid,
        "total": len(tasks),
        "data": [
            {
                "id": t.id,
                "task_type": t.task_type,
                "status": t.status,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "image_date": t.image_date,
                "image_source": t.image_source,
                "failure_reason": t.failure_reason,
                "retry_count": t.retry_count,
                "max_retries": t.max_retries,
                "created_at": t.created_at,
                "started_at": t.started_at,
                "completed_at": t.completed_at,
            }
            for t in tasks
        ],
    }


@router.get("/{uuid}", response_model=EventDetail)
def get_event(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    imagery_count_map = _build_imagery_count_map(db, [event.uuid])
    return _event_to_detail(event, imagery_count_map.get(event.uuid))


@router.post("/{uuid}/process", response_model=MessageResponse)
def trigger_process(
    uuid: str,
    background_tasks: BackgroundTasks,
    req: Optional[ProcessEventRequest] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    processable_statuses = {"pending", "pool", "checked", "queued"}
    if event.status not in processable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {event.status} 不支持手动推进",
        )

    selected_image_type = (req.image_type if req else None) or None
    if selected_image_type not in {None, "pre", "post"}:
        raise HTTPException(status_code=400, detail="image_type 仅支持 pre 或 post")

    if selected_image_type == "pre" and not event.pre_image_path:
        raise HTTPException(status_code=400, detail="当前事件没有可用的灾前影像")
    if selected_image_type == "post" and not event.post_image_path:
        raise HTTPException(status_code=400, detail="当前事件没有可用的灾后影像")

    existing_task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if existing_task and selected_image_type:
        from core.pool_manager import PoolManager
        pm = PoolManager(db)
        task_data = safe_json_loads(existing_task.task_data, {}) or {}
        rebuilt = pm._build_task_data(event, preferred_image_type=selected_image_type)
        task_data["image_path"] = rebuilt.get("image_path")
        task_data["image_kind"] = rebuilt.get("image_kind")
        task_data["selected_image_type"] = selected_image_type
        existing_task.task_data = json.dumps(task_data, ensure_ascii=False)
        if existing_task.status == "pending":
            initial_state = build_initial_progress_state(task_data)
            existing_task.progress_stage = initial_state["progress_stage"]
            existing_task.progress_message = "已切换手动选择影像，等待服务内部调度推理任务"
            existing_task.progress_percent = initial_state["progress_percent"]
            existing_task.current_step = initial_state["current_step"]
            existing_task.total_steps = initial_state["total_steps"]
            existing_task.step_details = initial_state["step_details"]
        existing_task.updated_at = int(datetime.now(timezone.utc).timestamp() * 1000)
        db.commit()

    def _run():
        from core.pool_manager import PoolManager
        from models.models import get_session_factory
        s = get_session_factory()()
        try:
            pm = PoolManager(s)
            fresh_event = s.query(Event).filter(Event.uuid == uuid).first()
            current_status = fresh_event.status if fresh_event else event.status
            if current_status == "pending":
                pm.process_pending_events(limit=1)
            elif current_status == "pool":
                pm.submit_gee_tasks_for_pool(limit=1)
                pm.assess_ready_events(limit=1)
            elif current_status == "checked":
                pm.enqueue_checked_events(limit=1, target_uuid=uuid, preferred_image_type=selected_image_type)
                pm.process_pending_inference_tasks(limit=1, target_uuid=uuid)
            elif current_status == "queued":
                pm.process_pending_inference_tasks(limit=1, target_uuid=uuid)
        finally:
            s.close()

    background_tasks.add_task(_run)
    return MessageResponse(message=f"事件 {uuid} 处理已触发，当前状态: {event.status}")
