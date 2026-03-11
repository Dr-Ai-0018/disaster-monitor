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
)
from utils.auth import get_api_token_entity

router = APIRouter(prefix="/api/tasks", tags=["任务队列"])


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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
        # 锁定任务
        tq.status = "locked"
        tq.locked_by = worker_id
        tq.locked_at = now
        tq.locked_until = now + lock_duration_ms
        tq.heartbeat = now
        tq.updated_at = now

        # 更新关联 event 状态
        event = db.query(Event).filter(Event.uuid == tq.uuid).first()
        if event and event.status == "queued":
            event.status = "processing"
            event.updated_at = now

        try:
            td_raw = json.loads(tq.task_data)
            task_data = TaskData(**td_raw)
        except Exception:
            continue

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
        TaskQueue.status == "locked",
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
    )


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
    ).first()

    if not tq:
        raise HTTPException(status_code=404, detail="任务不存在或未被该 Worker 锁定")

    now = _now_ms()
    retry_count = (tq.retry_count or 0) + 1
    max_retries = tq.max_retries or 3
    will_retry = req.can_retry and retry_count < max_retries

    tq.retry_count = retry_count
    tq.failure_reason = req.reason
    tq.updated_at = now

    if will_retry:
        tq.status = "pending"
        tq.locked_by = None
        tq.locked_at = None
        tq.locked_until = None
        tq.heartbeat = None
        # 回退事件状态
        event = db.query(Event).filter(Event.uuid == uuid).first()
        if event:
            event.status = "queued"
            event.updated_at = now
    else:
        tq.status = "failed"
        event = db.query(Event).filter(Event.uuid == uuid).first()
        if event:
            event.status = "checked"  # 允许重新入队
            event.updated_at = now

    db.commit()

    return FailTaskResponse(
        message="任务失败已记录",
        uuid=uuid,
        retry_count=retry_count,
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
        created_at=tq.created_at,
    )
