from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

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


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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


def derive_workflow_state(
    event: Event,
    task: Optional[TaskQueue],
    product: Optional[Product],
    image_review: Optional[ImageReview],
    summary_review: Optional[SummaryReview],
    report_candidate: Optional[ReportCandidate],
    daily_report: Optional[DailyReport],
) -> dict:
    has_any_image = bool(event.pre_image_path or event.post_image_path)
    state = {
        "current_pool": "event_pool",
        "pool_status": "await_imagery",
        "auto_stage": "event_ingest",
        "manual_stage": "image_review",
        "selected_image_type": None,
    }

    if not has_any_image:
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

    selected_image_type = image_review.selected_image_type or "post"
    if image_review.review_status == "rejected":
        state.update(
            {
                "current_pool": "image_review_pool",
                "pool_status": "image_rejected",
                "auto_stage": "imagery_download",
                "manual_stage": "image_review",
                "selected_image_type": selected_image_type,
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
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if task is None:
        state.update(
            {
                "current_pool": "inference_pool",
                "pool_status": "await_inference_trigger",
                "auto_stage": "imagery_download",
                "manual_stage": "trigger_inference",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    inference_status = task.status or "pending"
    if inference_status in {"pending", "queued"}:
        state.update(
            {
                "current_pool": "inference_pool",
                "pool_status": "await_inference_execution",
                "auto_stage": "imagery_download",
                "manual_stage": "trigger_inference",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if inference_status in {"running"}:
        state.update(
            {
                "current_pool": "inference_pool",
                "pool_status": "inference_running",
                "auto_stage": "imagery_download",
                "manual_stage": "trigger_inference",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if inference_status in {"failed", "paused", "pause_requested"}:
        state.update(
            {
                "current_pool": "inference_pool",
                "pool_status": "inference_needs_attention",
                "auto_stage": "imagery_download",
                "manual_stage": "trigger_inference",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if not product or not product.inference_result:
        state.update(
            {
                "current_pool": "inference_pool",
                "pool_status": "await_product_materialization",
                "auto_stage": "imagery_download",
                "manual_stage": "trigger_inference",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if not product.summary:
        state.update(
            {
                "current_pool": "summary_report_pool",
                "pool_status": "await_summary_generation",
                "auto_stage": "manual_gate",
                "manual_stage": "generate_summary",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if summary_review is None or summary_review.summary_status == "pending":
        state.update(
            {
                "current_pool": "summary_report_pool",
                "pool_status": "await_summary_review",
                "auto_stage": "manual_gate",
                "manual_stage": "review_summary",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if summary_review.summary_status == "rejected":
        state.update(
            {
                "current_pool": "summary_report_pool",
                "pool_status": "summary_rejected",
                "auto_stage": "manual_gate",
                "manual_stage": "generate_summary",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if report_candidate is None:
        state.update(
            {
                "current_pool": "summary_report_pool",
                "pool_status": "await_report_push",
                "auto_stage": "manual_gate",
                "manual_stage": "push_to_report",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    if daily_report is None:
        state.update(
            {
                "current_pool": "summary_report_pool",
                "pool_status": "ready_for_daily_report",
                "auto_stage": "manual_gate",
                "manual_stage": "generate_report",
                "selected_image_type": selected_image_type,
            }
        )
        return state

    state.update(
        {
            "current_pool": "summary_report_pool",
            "pool_status": "report_published" if daily_report.published else "report_draft_ready",
            "auto_stage": "manual_gate",
            "manual_stage": "generate_report",
            "selected_image_type": selected_image_type,
        }
    )
    return state


def sync_workflow_projection(db: Session) -> None:
    now = _now_ms()
    changed = False
    events = db.query(Event).all()
    for event in events:
        existing_item = db.query(WorkflowItem).filter(WorkflowItem.uuid == event.uuid).first()
        item = existing_item or ensure_workflow_item(db, event)
        if existing_item is None:
            changed = True
        task = db.query(TaskQueue).filter(TaskQueue.uuid == event.uuid).first()
        product = db.query(Product).filter(Product.uuid == event.uuid).first()
        image_review = latest_image_review(db, event.uuid)
        summary_review = db.query(SummaryReview).filter(SummaryReview.uuid == event.uuid).first()
        report_candidate = latest_report_candidate(db, event.uuid)
        daily_report = None
        if report_candidate:
            daily_report = db.query(DailyReport).filter(DailyReport.report_date == report_candidate.report_date).first()

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

    if changed:
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
    return affected


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
