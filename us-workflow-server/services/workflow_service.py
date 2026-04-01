from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models.models import Event, ImageReview, Product, ReportCandidate, SummaryReview, TaskQueue, WorkflowItem


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def ensure_workflow_item(db: Session, event: Event) -> WorkflowItem:
    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == event.uuid).first()
    now = _now_ms()
    if item:
        return item
    item = WorkflowItem(
        uuid=event.uuid,
        current_pool="event_pool",
        pool_status="pending",
        auto_stage="event_ingest",
        manual_stage="image_review",
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    return item


def derive_pool(
    event: Event,
    task: Optional[TaskQueue],
    product: Optional[Product],
    image_review: Optional[ImageReview],
    summary_review: Optional[SummaryReview],
    report_candidate: Optional[ReportCandidate],
) -> str:
    has_any_image = bool(event.pre_image_path or event.post_image_path)
    if not has_any_image:
        return "event_pool"
    if not bool(event.quality_checked):
        return "imagery_pool"
    if image_review is None or image_review.review_status in {"pending", "rejected"}:
        return "image_review_pool"
    if task is None or task.status in {"pending", "running", "failed", "paused", "pause_requested"}:
        return "inference_pool"
    if product is None:
        return "inference_pool"
    if summary_review is None or summary_review.summary_status in {"pending", "rejected"}:
        return "summary_report_pool"
    if report_candidate is None:
        return "summary_report_pool"
    return "summary_report_pool"


def sync_workflow_projection(db: Session) -> None:
    now = _now_ms()
    events = db.query(Event).all()
    for event in events:
        item = ensure_workflow_item(db, event)
        task = db.query(TaskQueue).filter(TaskQueue.uuid == event.uuid).first()
        product = db.query(Product).filter(Product.uuid == event.uuid).first()
        image_review = (
            db.query(ImageReview)
            .filter(ImageReview.uuid == event.uuid)
            .order_by(ImageReview.updated_at.desc(), ImageReview.id.desc())
            .first()
        )
        summary_review = db.query(SummaryReview).filter(SummaryReview.uuid == event.uuid).first()
        report_candidate = (
            db.query(ReportCandidate)
            .filter(ReportCandidate.uuid == event.uuid, ReportCandidate.included == 1)
            .order_by(ReportCandidate.updated_at.desc(), ReportCandidate.id.desc())
            .first()
        )
        item.current_pool = derive_pool(event, task, product, image_review, summary_review, report_candidate)
        item.pool_status = "ready" if item.current_pool in {"image_review_pool", "inference_pool", "summary_report_pool"} else "active"
        item.updated_at = now
    db.commit()


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
        task.progress_message = "已重置推理阶段，等待重新执行"
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
        workflow_item.current_pool = "image_review_pool"
        workflow_item.pool_status = "ready"
        workflow_item.updated_at = now

    event = db.query(Event).filter(Event.uuid == uuid).first()
    if event:
        event.status = "checked"
        event.updated_at = now

    db.commit()
    return affected


def reset_all_inference_stage(db: Session) -> int:
    total = 0
    uuids = {row.uuid for row in db.query(TaskQueue.uuid).all()} | {row.uuid for row in db.query(Product.uuid).all()}
    for uuid in uuids:
        total += reset_inference_content(db, uuid)
    return total
