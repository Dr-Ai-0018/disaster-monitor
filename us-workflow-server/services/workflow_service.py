from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import settings
from models.models import (
    DailyReport,
    Event,
    ImageReview,
    Product,
    ReportCandidate,
    SummaryReview,
    TaskQueue,
    WorkflowItem,
)

_PROJECTION_LOCK = Lock()
_PROJECTION_STATE = {
    "dirty": True,
    "last_full_sync_ms": 0,
}


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _has_real_imagery(event: Event) -> bool:
    return bool((event.pre_image_path and str(event.pre_image_path).strip()) or (event.post_image_path and str(event.post_image_path).strip()))


def _is_placeholder_inference(task: Optional[TaskQueue], product: Optional[Product]) -> bool:
    if task and task.progress_message and "无可用影像" in task.progress_message:
        return True

    payload = product.inference_result if product and product.inference_result else None
    if not payload:
        return False

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return "NO_IMAGE" in payload or "no usable imagery" in payload.lower()

    if isinstance(parsed, dict):
        if "00_NO_IMAGE" in parsed:
            return True
        for value in parsed.values():
            if isinstance(value, dict) and str(value.get("type") or "").upper() == "NO_IMAGE":
                return True

    return False


def mark_projection_dirty() -> None:
    with _PROJECTION_LOCK:
        _PROJECTION_STATE["dirty"] = True


def latest_image_review(db: Session, uuid: str) -> Optional[ImageReview]:
    return (
        db.query(ImageReview)
        .filter(ImageReview.uuid == uuid)
        .order_by(ImageReview.updated_at.desc(), ImageReview.id.desc())
        .first()
    )


def latest_report_candidate(db: Session, uuid: str) -> Optional[ReportCandidate]:
    return (
        db.query(ReportCandidate)
        .filter(ReportCandidate.uuid == uuid, ReportCandidate.included == 1)
        .order_by(ReportCandidate.updated_at.desc(), ReportCandidate.id.desc())
        .first()
    )


def ensure_workflow_item(db: Session, event: Event) -> WorkflowItem:
    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == event.uuid).first()
    now = _now_ms()
    if item:
        return item
    item = WorkflowItem(
        uuid=event.uuid,
        current_pool="event_pool",
        pool_status="await_imagery",
        auto_stage="event_ingest",
        manual_stage="image_review",
        created_at=now,
        updated_at=now,
        last_transition_at=now,
    )
    db.add(item)
    db.flush()
    return item


def _selected_image_type(image_review: Optional[ImageReview], task: Optional[TaskQueue]) -> Optional[str]:
    if image_review and image_review.selected_image_type:
        return image_review.selected_image_type

    if task and task.task_data:
        try:
            payload = json.loads(task.task_data)
        except json.JSONDecodeError:
            payload = {}
        selected = payload.get("selected_image_type")
        if selected in {"pre", "post"}:
            return selected
        image_kind = payload.get("image_kind")
        if image_kind == "pre_disaster":
            return "pre"
        if image_kind == "post_disaster":
            return "post"

    return None


def _derive_post_review_state(
    task: Optional[TaskQueue],
    product: Optional[Product],
    summary_review: Optional[SummaryReview],
    report_candidate: Optional[ReportCandidate],
    daily_report: Optional[DailyReport],
    selected_image_type: Optional[str],
) -> dict:
    selected = selected_image_type or "post"

    if task is None:
        return {
            "current_pool": "inference_pool",
            "pool_status": "await_inference_trigger",
            "auto_stage": "imagery_download",
            "manual_stage": "trigger_inference",
            "selected_image_type": selected,
        }

    inference_status = task.status or "pending"
    if inference_status in {"pending", "queued"}:
        return {
            "current_pool": "inference_pool",
            "pool_status": "await_inference_execution",
            "auto_stage": "imagery_download",
            "manual_stage": "trigger_inference",
            "selected_image_type": selected,
        }

    if inference_status in {"running"}:
        return {
            "current_pool": "inference_pool",
            "pool_status": "inference_running",
            "auto_stage": "imagery_download",
            "manual_stage": "trigger_inference",
            "selected_image_type": selected,
        }

    if inference_status in {"failed", "paused", "pause_requested"}:
        return {
            "current_pool": "inference_pool",
            "pool_status": "inference_needs_attention",
            "auto_stage": "imagery_download",
            "manual_stage": "trigger_inference",
            "selected_image_type": selected,
        }

    if not product or not product.inference_result:
        return {
            "current_pool": "inference_pool",
            "pool_status": "await_product_materialization",
            "auto_stage": "imagery_download",
            "manual_stage": "trigger_inference",
            "selected_image_type": selected,
        }

    if not product.summary:
        return {
            "current_pool": "summary_report_pool",
            "pool_status": "await_summary_generation",
            "auto_stage": "manual_gate",
            "manual_stage": "generate_summary",
            "selected_image_type": selected,
        }

    if summary_review is None or summary_review.summary_status == "pending":
        return {
            "current_pool": "summary_report_pool",
            "pool_status": "await_summary_review",
            "auto_stage": "manual_gate",
            "manual_stage": "review_summary",
            "selected_image_type": selected,
        }

    if summary_review.summary_status == "rejected":
        return {
            "current_pool": "summary_report_pool",
            "pool_status": "summary_rejected",
            "auto_stage": "manual_gate",
            "manual_stage": "generate_summary",
            "selected_image_type": selected,
        }

    if report_candidate is None:
        return {
            "current_pool": "summary_report_pool",
            "pool_status": "await_report_push",
            "auto_stage": "manual_gate",
            "manual_stage": "push_to_report",
            "selected_image_type": selected,
        }

    if daily_report is None:
        return {
            "current_pool": "summary_report_pool",
            "pool_status": "ready_for_daily_report",
            "auto_stage": "manual_gate",
            "manual_stage": "generate_report",
            "selected_image_type": selected,
        }

    return {
        "current_pool": "summary_report_pool",
        "pool_status": "report_published" if daily_report.published else "report_draft_ready",
        "auto_stage": "manual_gate",
        "manual_stage": "generate_report",
        "selected_image_type": selected,
    }


def derive_workflow_state(
    event: Event,
    task: Optional[TaskQueue],
    product: Optional[Product],
    image_review: Optional[ImageReview],
    summary_review: Optional[SummaryReview],
    report_candidate: Optional[ReportCandidate],
    daily_report: Optional[DailyReport],
) -> dict:
    selected_image_type = _selected_image_type(image_review, task)
    state = {
        "current_pool": "event_pool",
        "pool_status": "await_imagery",
        "auto_stage": "event_ingest",
        "manual_stage": "image_review",
        "selected_image_type": selected_image_type,
    }

    # Legacy compatibility: some historical rows already completed inference/materialization
    # before workflow/image review tables existed, so they must not be pushed back to
    # event/image-review pools even if imagery paths or review rows are missing now.
    if task is not None or product is not None:
        return _derive_post_review_state(
            task=task,
            product=product,
            summary_review=summary_review,
            report_candidate=report_candidate,
            daily_report=daily_report,
            selected_image_type=selected_image_type,
        )

    has_any_image = bool(event.pre_image_path or event.post_image_path)
    if not has_any_image:
        if event.status == "pool":
            return {
                "current_pool": "imagery_pool",
                "pool_status": "await_imagery_preparation",
                "auto_stage": "imagery_download",
                "manual_stage": "image_review",
                "selected_image_type": selected_image_type,
            }
        return state

    if not bool(event.quality_checked):
        state.update(
            {
                "current_pool": "imagery_pool",
                "pool_status": "imagery_ready_pending_quality",
                "auto_stage": "imagery_download",
                "manual_stage": "image_review",
            }
        )
        return state

    if image_review is None:
        state.update(
            {
                "current_pool": "image_review_pool",
                "pool_status": "await_image_review",
                "auto_stage": "imagery_download",
                "manual_stage": "image_review",
            }
        )
        return state

    if image_review.review_status == "rejected":
        state.update(
            {
                "current_pool": "image_review_pool",
                "pool_status": "image_rejected",
                "auto_stage": "imagery_download",
                "manual_stage": "image_review",
                "selected_image_type": selected_image_type or "post",
            }
        )
        return state

    if image_review.review_status != "approved":
        state.update(
            {
                "current_pool": "image_review_pool",
                "pool_status": "await_image_review",
                "auto_stage": "imagery_download",
                "manual_stage": "image_review",
                "selected_image_type": selected_image_type or "post",
            }
        )
        return state
    return _derive_post_review_state(
        task=task,
        product=product,
        summary_review=summary_review,
        report_candidate=report_candidate,
        daily_report=daily_report,
        selected_image_type=selected_image_type,
    )


def sync_workflow_projection(db: Session) -> None:
    sync_workflow_projection_if_needed(db, force=True)


def sync_workflow_projection_if_needed(db: Session, force: bool = False) -> None:
    now = _now_ms()
    with _PROJECTION_LOCK:
        if not force:
            last_sync_ms = int(_PROJECTION_STATE["last_full_sync_ms"])
            is_dirty = bool(_PROJECTION_STATE["dirty"])
            if (not is_dirty) and (now - last_sync_ms < settings.WORKFLOW_PROJECTION_REFRESH_INTERVAL_MS):
                return

        changed = _sync_workflow_projection_impl(db)
        _PROJECTION_STATE["last_full_sync_ms"] = now
        _PROJECTION_STATE["dirty"] = False
        if changed:
            db.commit()


def _sync_workflow_projection_impl(db: Session) -> bool:
    now = _now_ms()
    changed = False
    events = db.query(Event).all()
    if not events:
        return False

    uuids = [event.uuid for event in events]
    workflow_items = {item.uuid: item for item in db.query(WorkflowItem).filter(WorkflowItem.uuid.in_(uuids)).all()}
    tasks = {item.uuid: item for item in db.query(TaskQueue).filter(TaskQueue.uuid.in_(uuids)).all()}
    products = {item.uuid: item for item in db.query(Product).filter(Product.uuid.in_(uuids)).all()}
    summary_reviews = {item.uuid: item for item in db.query(SummaryReview).filter(SummaryReview.uuid.in_(uuids)).all()}

    image_reviews: dict[str, ImageReview] = {}
    for row in (
        db.query(ImageReview)
        .filter(ImageReview.uuid.in_(uuids))
        .order_by(ImageReview.uuid.asc(), ImageReview.updated_at.desc(), ImageReview.id.desc())
        .all()
    ):
        image_reviews.setdefault(row.uuid, row)

    report_candidates: dict[str, ReportCandidate] = {}
    for row in (
        db.query(ReportCandidate)
        .filter(ReportCandidate.uuid.in_(uuids), ReportCandidate.included == 1)
        .order_by(ReportCandidate.uuid.asc(), ReportCandidate.updated_at.desc(), ReportCandidate.id.desc())
        .all()
    ):
        report_candidates.setdefault(row.uuid, row)

    report_dates = {item.report_date for item in report_candidates.values()}
    daily_reports = {}
    if report_dates:
        daily_reports = {
            item.report_date: item
            for item in db.query(DailyReport).filter(DailyReport.report_date.in_(report_dates)).all()
        }

    for event in events:
        existing_item = workflow_items.get(event.uuid)
        item = existing_item or ensure_workflow_item(db, event)
        if existing_item is None:
            workflow_items[event.uuid] = item
            changed = True
        task = tasks.get(event.uuid)
        product = products.get(event.uuid)
        image_review = image_reviews.get(event.uuid)
        summary_review = summary_reviews.get(event.uuid)
        report_candidate = report_candidates.get(event.uuid)
        daily_report = daily_reports.get(report_candidate.report_date) if report_candidate else None

        state = derive_workflow_state(
            event=event,
            task=task,
            product=product,
            image_review=image_review,
            summary_review=summary_review,
            report_candidate=report_candidate,
            daily_report=daily_report,
        )
        pool_changed = item.current_pool != state["current_pool"] or item.pool_status != state["pool_status"]
        field_changed = (
            pool_changed
            or item.auto_stage != state["auto_stage"]
            or item.manual_stage != state["manual_stage"]
            or item.selected_image_type != state["selected_image_type"]
        )
        if not field_changed:
            continue

        item.current_pool = state["current_pool"]
        item.pool_status = state["pool_status"]
        item.auto_stage = state["auto_stage"]
        item.manual_stage = state["manual_stage"]
        item.selected_image_type = state["selected_image_type"]
        item.updated_at = now
        if pool_changed or not item.last_transition_at:
            item.last_transition_at = now
        changed = True

    return changed


def reset_inference_content(db: Session, uuid: str) -> int:
    affected = 0
    now = _now_ms()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    if product:
        db.delete(product)
        affected += 1

    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if task:
        task.status = "pending"
        task.retry_count = 0
        task.failure_reason = None
        task.last_error_details = None
        task.locked_by = None
        task.locked_at = None
        task.locked_until = None
        task.heartbeat = None
        task.completed_at = None
        task.progress_stage = "queued"
        task.progress_message = "已清空成品与摘要，等待手动重新触发推理"
        task.progress_percent = 0
        task.current_step = 0
        task.updated_at = now
        affected += 1

    summary_review = db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first()
    if summary_review:
        db.delete(summary_review)
        affected += 1

    report_rows = db.query(ReportCandidate).filter(ReportCandidate.uuid == uuid).all()
    for row in report_rows:
        db.delete(row)
        affected += 1

    workflow_item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if workflow_item:
        workflow_item.current_pool = "inference_pool"
        workflow_item.pool_status = "await_inference_trigger"
        workflow_item.manual_stage = "trigger_inference"
        workflow_item.updated_at = now
        workflow_item.last_transition_at = now

    event = db.query(Event).filter(Event.uuid == uuid).first()
    if event:
        event.status = "checked"
        event.updated_at = now

    db.commit()
    mark_projection_dirty()
    return affected


def _delete_report_candidates(db: Session, uuid: str) -> int:
    affected = 0
    for row in db.query(ReportCandidate).filter(ReportCandidate.uuid == uuid).all():
        db.delete(row)
        affected += 1
    return affected


def _delete_image_reviews(db: Session, uuid: str) -> int:
    affected = 0
    for row in db.query(ImageReview).filter(ImageReview.uuid == uuid).all():
        db.delete(row)
        affected += 1
    return affected


def _delete_task_queue_row(db: Session, uuid: str) -> int:
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    if not task:
        return 0
    db.delete(task)
    return 1


def _delete_product_row(db: Session, uuid: str) -> int:
    product = db.query(Product).filter(Product.uuid == uuid).first()
    if not product:
        return 0
    db.delete(product)
    return 1


def _delete_summary_review_row(db: Session, uuid: str) -> int:
    summary_review = db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first()
    if not summary_review:
        return 0
    db.delete(summary_review)
    return 1


def _clear_imagery_state(event: Event) -> None:
    event.pre_image_path = None
    event.pre_image_date = None
    event.pre_image_downloaded = 0
    event.pre_image_source = None
    event.post_image_path = None
    event.post_image_date = None
    event.post_image_downloaded = 0
    event.post_image_source = None
    event.quality_score = None
    event.quality_assessment = None
    event.quality_checked = 0
    event.quality_pass = 0
    event.quality_check_time = None
    event.pre_window_days = 7
    event.pre_imagery_last_check = None
    event.pre_imagery_exhausted = 0
    event.post_window_days = 7
    event.post_imagery_last_check = None
    event.post_imagery_open = 1
    event.imagery_check_count = 0


def _set_workflow_item_state(
    workflow_item: Optional[WorkflowItem],
    *,
    current_pool: str,
    pool_status: str,
    auto_stage: str,
    manual_stage: str,
    operator: Optional[str],
    now: int,
) -> None:
    if not workflow_item:
        return
    workflow_item.current_pool = current_pool
    workflow_item.pool_status = pool_status
    workflow_item.auto_stage = auto_stage
    workflow_item.manual_stage = manual_stage
    workflow_item.selected_image_type = None
    workflow_item.last_operator = operator
    workflow_item.updated_at = now
    workflow_item.last_transition_at = now


def _rollback_to_target_pool(
    db: Session,
    uuid: str,
    *,
    target_pool: str,
    operator: Optional[str] = None,
    commit: bool = True,
) -> dict:
    now = _now_ms()
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise ValueError(f"事件不存在: {uuid}")

    workflow_item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if not workflow_item:
        workflow_item = ensure_workflow_item(db, event)

    requested_target = target_pool
    if target_pool == "image_review_pool" and not _has_real_imagery(event):
        target_pool = "imagery_pool"

    before_pool = workflow_item.current_pool
    before_status = workflow_item.pool_status
    affected = 0

    affected += _delete_report_candidates(db, uuid)
    affected += _delete_summary_review_row(db, uuid)

    if target_pool in {"image_review_pool", "imagery_pool", "event_pool", "inference_pool"}:
        affected += _delete_product_row(db, uuid)
        affected += _delete_task_queue_row(db, uuid)

    if target_pool in {"image_review_pool", "imagery_pool", "event_pool"}:
        affected += _delete_image_reviews(db, uuid)

    if target_pool == "event_pool":
        _clear_imagery_state(event)
        event.status = "pending"
        event.updated_at = now
        _set_workflow_item_state(
            workflow_item,
            current_pool="event_pool",
            pool_status="await_imagery",
            auto_stage="event_ingest",
            manual_stage="image_review",
            operator=operator,
            now=now,
        )
    elif target_pool == "imagery_pool":
        _clear_imagery_state(event)
        event.status = "pool"
        event.updated_at = now
        _set_workflow_item_state(
            workflow_item,
            current_pool="imagery_pool",
            pool_status="await_imagery_preparation",
            auto_stage="imagery_download",
            manual_stage="image_review",
            operator=operator,
            now=now,
        )
    elif target_pool == "image_review_pool":
        event.status = "checked"
        event.updated_at = now
        _set_workflow_item_state(
            workflow_item,
            current_pool="image_review_pool",
            pool_status="await_image_review",
            auto_stage="imagery_download",
            manual_stage="image_review",
            operator=operator,
            now=now,
        )
    elif target_pool == "inference_pool":
        event.status = "checked"
        event.updated_at = now
        _set_workflow_item_state(
            workflow_item,
            current_pool="inference_pool",
            pool_status="await_inference_trigger",
            auto_stage="imagery_download",
            manual_stage="trigger_inference",
            operator=operator,
            now=now,
        )
    else:
        raise ValueError(f"unsupported rollback target: {requested_target}")

    if commit:
        db.commit()
        mark_projection_dirty()

    return {
        "uuid": uuid,
        "affected": affected,
        "before_pool": before_pool,
        "before_status": before_status,
        "after_pool": workflow_item.current_pool,
        "after_status": workflow_item.pool_status,
        "requested_target": requested_target,
    }


def rollback_to_previous_pool(
    db: Session,
    uuid: str,
    *,
    operator: Optional[str] = None,
    commit: bool = True,
) -> dict:
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise ValueError(f"事件不存在: {uuid}")

    workflow_item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    current_pool = workflow_item.current_pool if workflow_item else derive_workflow_state(
        event=event,
        task=db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first(),
        product=db.query(Product).filter(Product.uuid == uuid).first(),
        image_review=latest_image_review(db, uuid),
        summary_review=db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first(),
        report_candidate=latest_report_candidate(db, uuid),
        daily_report=None,
    )["current_pool"]

    if current_pool == "summary_report_pool":
        target_pool = "inference_pool"
    elif current_pool == "inference_pool":
        target_pool = "image_review_pool"
    elif current_pool == "image_review_pool":
        target_pool = "imagery_pool"
    elif current_pool == "imagery_pool":
        target_pool = "event_pool"
    else:
        raise ValueError(f"{uuid} 当前池子 {current_pool} 不支持回退上一池")

    return _rollback_to_target_pool(db, uuid, target_pool=target_pool, operator=operator, commit=commit)


def rollback_to_reaudit_pool(
    db: Session,
    uuid: str,
    *,
    operator: Optional[str] = None,
    commit: bool = True,
) -> dict:
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise ValueError(f"事件不存在: {uuid}")

    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    target_pool = "imagery_pool" if (_is_placeholder_inference(task, product) or not _has_real_imagery(event)) else "image_review_pool"
    return _rollback_to_target_pool(db, uuid, target_pool=target_pool, operator=operator, commit=commit)


def reset_workflow_stage(db: Session, uuid: str, stage: str) -> int:
    stage = (stage or "").strip()
    if stage not in {"image_review", "inference", "summary"}:
        raise ValueError(f"unsupported stage: {stage}")

    affected = 0
    now = _now_ms()

    event = db.query(Event).filter(Event.uuid == uuid).first()
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    workflow_item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    summary_review = db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first()
    image_review = latest_image_review(db, uuid)
    report_rows = db.query(ReportCandidate).filter(ReportCandidate.uuid == uuid).all()

    if stage in {"image_review", "inference"}:
        if product:
            db.delete(product)
            affected += 1

        if task:
            task.status = "pending"
            task.retry_count = 0
            task.failure_reason = None
            task.last_error_details = None
            task.locked_by = None
            task.locked_at = None
            task.locked_until = None
            task.heartbeat = None
            task.completed_at = None
            task.progress_stage = "queued"
            task.progress_message = (
                "已回退到影像审核阶段，等待重新审核"
                if stage == "image_review"
                else "已回退到推理阶段，等待重新执行"
            )
            task.progress_percent = 0
            task.current_step = 0
            task.updated_at = now
            affected += 1

    if stage == "summary" and product:
        if product.summary:
            affected += 1
        product.summary = None
        product.summary_generated = 0
        product.summary_generated_at = None
        product.updated_at = now

    if summary_review:
        db.delete(summary_review)
        affected += 1

    for row in report_rows:
        db.delete(row)
        affected += 1

    if stage == "image_review" and image_review:
        image_review.review_status = "pending"
        image_review.human_decision = None
        image_review.reviewed_by = None
        image_review.reviewed_at = None
        image_review.updated_at = now
        affected += 1

    if workflow_item:
        if stage == "image_review":
            workflow_item.current_pool = "image_review_pool"
            workflow_item.pool_status = "await_image_review"
            workflow_item.manual_stage = "image_review"
        elif stage == "inference":
            workflow_item.current_pool = "inference_pool"
            workflow_item.pool_status = "await_inference_trigger"
            workflow_item.manual_stage = "trigger_inference"
        else:
            workflow_item.current_pool = "summary_report_pool"
            workflow_item.pool_status = "await_summary_generation"
            workflow_item.manual_stage = "generate_summary"
        workflow_item.updated_at = now
        workflow_item.last_transition_at = now

    if event:
        event.status = "checked"
        event.updated_at = now

    db.commit()
    mark_projection_dirty()
    return affected


def reset_all_inference_stage(db: Session, uuids: Optional[list[str]] = None) -> int:
    total = 0
    if uuids is None:
        uuids = sorted(
            {row.uuid for row in db.query(TaskQueue.uuid).all()} | {row.uuid for row in db.query(Product.uuid).all()}
        )
    for uuid in uuids:
        total += reset_inference_content(db, uuid)
    return total
