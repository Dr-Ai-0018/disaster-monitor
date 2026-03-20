"""
任务队列 API 路由（GPU 服务器使用）
"""
import json
import math
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.models import ApiToken, Event, TaskQueue, Product, get_db
from schemas.schemas import (
    PullTasksResponse, TaskItem, TaskData,
    HeartbeatRequest, HeartbeatResponse,
    SubmitResultRequest, SubmitResultResponse,
    FailTaskRequest, FailTaskResponse,
    TaskStatusResponse,
    TaskProgressUpdateRequest, TaskProgressUpdateResponse,
    TaskPauseAckRequest, TaskPauseAckResponse,
)
from utils.auth import get_api_token_entity
from utils.task_progress import build_initial_progress_state, get_total_steps

router = APIRouter(prefix="/api/tasks", tags=["任务队列"])


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _clamp_progress(value: int) -> int:
    return max(0, min(100, int(value)))


def _reset_task_for_retry(
    tq: TaskQueue,
    event: Optional[Event],
    now: int,
    message: str,
):
    state = build_initial_progress_state(tq.task_data)
    tq.status = "pending"
    tq.locked_by = None
    tq.locked_at = None
    tq.locked_until = None
    tq.heartbeat = None
    tq.pause_requested = 0
    tq.paused_at = None
    tq.completed_at = None
    tq.progress_stage = state["progress_stage"]
    tq.progress_message = message
    tq.progress_percent = state["progress_percent"]
    tq.current_step = state["current_step"]
    tq.total_steps = state["total_steps"]
    tq.step_details = state["step_details"]
    tq.updated_at = now
    if event:
        event.status = "queued"
        event.updated_at = now


@router.get("/pull", response_model=PullTasksResponse)
def pull_tasks(
    worker_id: str = Query(..., description="Worker 唯一标识"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    """拉取待处理任务并自动锁定"""
    now = _now_ms()
    lock_duration_ms = 7200 * 1000  # 2小时

    # 查找可用任务（pending 或锁已超时）
    candidates = (
        db.query(TaskQueue)
        .filter(
            TaskQueue.status == "pending",
        )
        .filter(
            (TaskQueue.locked_until == None) | (TaskQueue.locked_until < now)
        )
        .order_by(TaskQueue.priority.desc(), TaskQueue.created_at.asc())
        .limit(limit)
        .all()
    )

    tasks_out = []
    for tq in candidates:
        event = db.query(Event).filter(Event.uuid == tq.uuid).first()

        try:
            td_raw = json.loads(tq.task_data)
            task_data = TaskData(**td_raw)
        except Exception as exc:
            tq.status = "failed"
            tq.failure_reason = "任务数据损坏，无法下发给 Worker"
            tq.last_error_details = str(exc)
            tq.progress_stage = "failed"
            tq.progress_message = "任务数据校验失败，请检查 task_data"
            tq.locked_by = None
            tq.locked_at = None
            tq.locked_until = None
            tq.heartbeat = None
            tq.pause_requested = 0
            tq.paused_at = None
            tq.updated_at = now
            if event:
                event.status = "failed"
                event.updated_at = now
            continue

        if not tq.total_steps:
            tq.total_steps = get_total_steps(tq.task_data)
        if not tq.step_details:
            tq.step_details = build_initial_progress_state(tq.task_data)["step_details"]

        # 锁定任务
        tq.status = "locked"
        tq.locked_by = worker_id
        tq.locked_at = now
        tq.locked_until = now + lock_duration_ms
        tq.heartbeat = now
        tq.pause_requested = 0
        tq.progress_stage = "claimed"
        tq.progress_message = f"Worker {worker_id} 已接单，准备开始执行"
        tq.progress_percent = max(tq.progress_percent or 0, 1)
        tq.updated_at = now

        # 更新关联 event 状态
        if event and event.status in {"queued", "failed"}:
            event.status = "processing"
            event.updated_at = now

        tasks_out.append(
            TaskItem(
                id=tq.id,
                uuid=tq.uuid,
                priority=tq.priority or 0,
                task_data=task_data,
                locked_by=tq.locked_by,
                locked_until=tq.locked_until,
                created_at=tq.created_at,
            )
        )

    db.commit()
    return PullTasksResponse(tasks=tasks_out, count=len(tasks_out))


@router.put("/{uuid}/heartbeat", response_model=HeartbeatResponse)
def update_heartbeat(
    uuid: str,
    req: HeartbeatRequest,
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    """更新任务心跳，防止锁超时"""
    tq = db.query(TaskQueue).filter(
        TaskQueue.uuid == uuid,
        TaskQueue.locked_by == req.worker_id,
        TaskQueue.status.in_(["locked", "pause_requested"]),
    ).first()

    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在或未被该 Worker 锁定")

    now = _now_ms()
    tq.heartbeat = now
    # 延长锁定时间
    tq.locked_until = now + (tq.lock_duration or 7200) * 1000
    tq.updated_at = now
    db.commit()

    return HeartbeatResponse(
        message="心跳更新成功",
        uuid=uuid,
        heartbeat=now,
        locked_until=tq.locked_until,
        should_pause=bool(tq.pause_requested),
    )


@router.put("/{uuid}/progress", response_model=TaskProgressUpdateResponse)
def update_task_progress(
    uuid: str,
    req: TaskProgressUpdateRequest,
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    """Worker 上报任务进度"""
    tq = db.query(TaskQueue).filter(
        TaskQueue.uuid == uuid,
        TaskQueue.locked_by == req.worker_id,
        TaskQueue.status.in_(["locked", "pause_requested"]),
    ).first()

    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在或未被该 Worker 锁定")

    now = _now_ms()
    total_steps = req.total_steps or tq.total_steps or get_total_steps(tq.task_data)
    current_step = max(req.current_step or 0, 0)
    if req.progress_percent is None:
        progress_percent = math.floor((current_step / max(total_steps, 1)) * 100)
    else:
        progress_percent = req.progress_percent

    tq.progress_stage = req.stage
    tq.progress_message = req.message
    tq.current_step = current_step
    tq.total_steps = total_steps
    tq.progress_percent = _clamp_progress(progress_percent)
    tq.heartbeat = now
    tq.locked_until = now + (tq.lock_duration or 7200) * 1000
    tq.updated_at = now
    if req.step_details is not None:
        tq.step_details = json.dumps(req.step_details, ensure_ascii=False)

    db.commit()

    return TaskProgressUpdateResponse(
        message="进度更新成功",
        uuid=uuid,
        should_pause=bool(tq.pause_requested),
        progress_percent=tq.progress_percent or 0,
        current_step=tq.current_step or 0,
        total_steps=tq.total_steps or total_steps,
    )


@router.put("/{uuid}/pause-ack", response_model=TaskPauseAckResponse)
def acknowledge_pause(
    uuid: str,
    req: TaskPauseAckRequest,
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    """Worker 确认暂停请求并释放任务锁"""
    tq = db.query(TaskQueue).filter(
        TaskQueue.uuid == uuid,
        TaskQueue.locked_by == req.worker_id,
        TaskQueue.status.in_(["locked", "pause_requested"]),
    ).first()

    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在或未被该 Worker 锁定")

    now = _now_ms()
    event = db.query(Event).filter(Event.uuid == uuid).first()

    tq.status = "paused"
    tq.pause_requested = 0
    tq.paused_at = now
    tq.locked_by = None
    tq.locked_at = None
    tq.locked_until = None
    tq.heartbeat = None
    tq.progress_stage = "paused"
    tq.progress_message = req.message or "任务已按请求暂停，等待人工继续"
    tq.current_step = req.current_step or tq.current_step or 0
    tq.total_steps = req.total_steps or tq.total_steps or get_total_steps(tq.task_data)
    tq.progress_percent = min(tq.progress_percent or 0, 99)
    tq.updated_at = now
    if req.step_details is not None:
        tq.step_details = json.dumps(req.step_details, ensure_ascii=False)

    if event:
        event.status = "queued"
        event.updated_at = now

    db.commit()
    return TaskPauseAckResponse(message="任务已暂停", uuid=uuid, status="paused")


@router.put("/{uuid}/result", response_model=SubmitResultResponse)
def submit_result(
    uuid: str,
    req: SubmitResultRequest,
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    """提交推理结果（幂等操作）"""
    tq = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在")

    now = _now_ms()
    inference_json = json.dumps(
        {k: v.dict() for k, v in req.inference_result.items()},
        ensure_ascii=False,
    )

    # 检查成品池是否已存在（幂等）
    existing_product = db.query(Product).filter(Product.uuid == uuid).first()
    created = existing_product is None

    # 获取事件信息
    event = db.query(Event).filter(Event.uuid == uuid).first()
    event_details_json = "{}"
    event_title = ""
    event_category = ""
    event_country = ""
    pre_date = None
    post_date = None

    if event:
        event_details_json = event.details_json or "{}"
        event_title = event.title or ""
        event_category = event.category or ""
        event_country = event.country or ""
        pre_date = event.pre_image_date
        post_date = event.post_image_date

    if existing_product:
        existing_product.inference_result = inference_json
        existing_product.updated_at = now
    else:
        product = Product(
            uuid=uuid,
            inference_result=inference_json,
            event_details=event_details_json,
            event_title=event_title,
            event_category=event_category,
            event_country=event_country,
            pre_image_date=pre_date,
            post_image_date=post_date,
            created_at=now,
            updated_at=now,
        )
        db.add(product)

    # 更新任务队列状态
    tq.status = "completed"
    tq.completed_at = now
    tq.failure_reason = None
    tq.last_error_details = None
    tq.pause_requested = 0
    tq.paused_at = None
    tq.locked_by = None
    tq.locked_at = None
    tq.locked_until = None
    tq.heartbeat = now
    tq.progress_stage = "completed"
    tq.progress_message = "推理结果已提交并写入成品池"
    tq.total_steps = tq.total_steps or get_total_steps(tq.task_data)
    tq.current_step = tq.total_steps
    tq.progress_percent = 100
    tq.updated_at = now

    # 更新事件状态
    if event:
        event.status = "completed"
        event.updated_at = now

    db.commit()

    return SubmitResultResponse(
        message="结果已接收" if created else "结果已更新",
        uuid=uuid,
        status="completed",
        created=created,
    )


@router.put("/{uuid}/fail", response_model=FailTaskResponse)
def fail_task(
    uuid: str,
    req: FailTaskRequest,
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    """报告任务失败"""
    tq = db.query(TaskQueue).filter(
        TaskQueue.uuid == uuid,
        TaskQueue.locked_by == req.worker_id,
        TaskQueue.status.in_(["locked", "pause_requested"]),
    ).first()

    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在或未被该 Worker 锁定")

    now = _now_ms()
    current_retry_count = tq.retry_count or 0
    max_retries = tq.max_retries or 3
    will_retry = req.can_retry and current_retry_count < max_retries

    tq.failure_reason = req.reason
    tq.last_error_details = req.error_details
    tq.updated_at = now

    event = db.query(Event).filter(Event.uuid == uuid).first()
    if will_retry:
        tq.retry_count = current_retry_count + 1
        _reset_task_for_retry(
            tq,
            event,
            now,
            message=f"任务失败，等待第 {tq.retry_count} 次自动重试",
        )
    else:
        tq.retry_count = current_retry_count
        tq.status = "failed"
        tq.locked_by = None
        tq.locked_at = None
        tq.locked_until = None
        tq.heartbeat = None
        tq.pause_requested = 0
        tq.paused_at = None
        tq.progress_stage = "failed"
        tq.progress_message = "连续失败已达到上限，任务已自动停止"
        tq.progress_percent = min(tq.progress_percent or 0, 99)
        if event:
            event.status = "failed"
            event.updated_at = now

    db.commit()

    return FailTaskResponse(
        message="任务失败已记录",
        uuid=uuid,
        retry_count=tq.retry_count or 0,
        will_retry=will_retry,
    )


@router.get("/{uuid}/status", response_model=TaskStatusResponse)
def get_task_status(
    uuid: str,
    db: Session = Depends(get_db),
    _token: ApiToken = Depends(get_api_token_entity),
):
    tq = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在")

    return TaskStatusResponse(
        uuid=uuid,
        status=tq.status,
        locked_by=tq.locked_by,
        locked_at=tq.locked_at,
        locked_until=tq.locked_until,
        heartbeat=tq.heartbeat,
        retry_count=tq.retry_count or 0,
        max_retries=tq.max_retries or 3,
        pause_requested=bool(tq.pause_requested),
        progress_stage=tq.progress_stage,
        progress_message=tq.progress_message,
        progress_percent=tq.progress_percent or 0,
        current_step=tq.current_step or 0,
        total_steps=tq.total_steps or get_total_steps(tq.task_data),
        created_at=tq.created_at,
    )
