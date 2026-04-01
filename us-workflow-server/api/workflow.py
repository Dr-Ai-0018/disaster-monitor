from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config.settings import settings
from models.models import Event, ImageReview, Product, ReportCandidate, SummaryReview, TaskQueue, WorkflowItem, get_db
from schemas.schemas import (
    ImageReviewDecisionRequest,
    ResetResponse,
    SummaryApprovalRequest,
    WorkflowItemListResponse,
    WorkflowItemResponse,
    WorkflowOverviewCard,
    WorkflowOverviewResponse,
)
from services.workflow_service import ensure_workflow_item, reset_all_inference_stage, reset_inference_content, sync_workflow_projection
from utils.auth import get_current_admin

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _quality_label(review: ImageReview | None) -> str:
    if not review:
        return "待审核"
    mapping = {"approved": "已通过", "rejected": "已打回", "pending": "待审核"}
    return mapping.get(review.review_status or "pending", review.review_status or "待审核")


def _summary_label(product: Product | None, summary_review: SummaryReview | None) -> str:
    if not product:
        return "无成品"
    if not product.summary:
        return "待生成摘要"
    if not summary_review:
        return "待人工审核"
    mapping = {"approved": "已准入日报", "rejected": "摘要已打回", "pending": "待人工审核"}
    return mapping.get(summary_review.summary_status or "pending", summary_review.summary_status or "待人工审核")


def _item_payload(db: Session, event: Event) -> WorkflowItemResponse:
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
    workflow_item = ensure_workflow_item(db, event)
    return WorkflowItemResponse(
        uuid=event.uuid,
        title=event.title,
        country=event.country,
        severity=event.severity,
        event_status=event.status,
        pool=workflow_item.current_pool,
        imagery="已就绪" if (event.pre_image_path or event.post_image_path) else "待下载",
        quality=_quality_label(image_review),
        inference=(task.status if task else "待创建"),
        summary=_summary_label(product, summary_review),
        report_candidate="已入候选" if report_candidate else "未入候选",
        updated_at=event.updated_at,
    )


@router.get("/overview", response_model=WorkflowOverviewResponse)
def workflow_overview(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    sync_workflow_projection(db)
    descriptions = {
        "event_pool": ("自动", "抓取事件、补经纬度、补详情、自动维护总列表"),
        "imagery_pool": ("自动", "自动提交并跟踪 GEE 下载，不需要人工干预"),
        "image_review_pool": ("手动", "Grok / 人工审核影像是否可进入推理"),
        "inference_pool": ("手动", "确认后触发 Latest Model 推理"),
        "summary_report_pool": ("手动", "摘要审核、日报候选、日报生成与发布"),
    }
    cards = []
    for key, label in [
        ("event_pool", "事件池"),
        ("imagery_pool", "影像池"),
        ("image_review_pool", "影像审核池"),
        ("inference_pool", "推理池"),
        ("summary_report_pool", "摘要日报池"),
    ]:
        count = db.query(WorkflowItem).filter(WorkflowItem.current_pool == key).count()
        auto_mode, description = descriptions[key]
        cards.append(
            WorkflowOverviewCard(
                key=key,
                label=label,
                total=count,
                auto_mode=auto_mode,
                description=description,
            )
        )
    return WorkflowOverviewResponse(
        cards=cards,
        scheduler_enabled=settings.ENABLE_SCHEDULER,
        legacy_root=str(settings.LEGACY_ROOT),
        database_path=settings.DATABASE_PATH,
    )


@router.get("/items", response_model=WorkflowItemListResponse)
def list_workflow_items(
    pool: str = Query("event_pool"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    sync_workflow_projection(db)
    rows = (
        db.query(Event)
        .join(WorkflowItem, WorkflowItem.uuid == Event.uuid)
        .filter(WorkflowItem.current_pool == pool)
        .order_by(Event.updated_at.desc())
        .limit(limit)
        .all()
    )
    return WorkflowItemListResponse(total=len(rows), data=[_item_payload(db, event) for event in rows])


@router.post("/items/{uuid}/reset-inference", response_model=ResetResponse)
def reset_item_inference(
    uuid: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    affected = reset_inference_content(db, uuid)
    if affected == 0:
        raise HTTPException(status_code=404, detail="未找到可重置的推理/摘要内容")
    return ResetResponse(message="已清空成品与推理阶段内容", affected=affected)


@router.post("/reset-inference-all", response_model=ResetResponse)
def reset_inference_all(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    affected = reset_all_inference_stage(db)
    return ResetResponse(message="已批量重置所有推理/摘要阶段内容", affected=affected)


@router.post("/items/{uuid}/image-review", response_model=ResetResponse)
def decide_image_review(
    uuid: str,
    req: ImageReviewDecisionRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    now = _now_ms()
    review = (
        db.query(ImageReview)
        .filter(ImageReview.uuid == uuid)
        .order_by(ImageReview.updated_at.desc(), ImageReview.id.desc())
        .first()
    )
    if not review:
        review = ImageReview(
            uuid=uuid,
            selected_image_type=req.image_type or "post",
            review_status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(review)
    review.selected_image_type = req.image_type or review.selected_image_type or "post"
    review.human_decision = "approved" if req.approved else "rejected"
    review.review_status = "approved" if req.approved else "rejected"
    review.ai_reason = req.reason or review.ai_reason
    review.reviewed_by = admin.username
    review.reviewed_at = now
    review.updated_at = now

    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if item:
        item.current_pool = "inference_pool" if req.approved else "image_review_pool"
        item.pool_status = "ready"
        item.last_operator = admin.username
        item.updated_at = now
    db.commit()
    return ResetResponse(message="影像审核结果已写入", affected=1)


@router.post("/items/{uuid}/summary-approval", response_model=ResetResponse)
def approve_summary(
    uuid: str,
    req: SummaryApprovalRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    now = _now_ms()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    if not product or not product.summary:
        raise HTTPException(status_code=400, detail="当前没有可审核的摘要")

    review = db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first()
    if not review:
        review = SummaryReview(uuid=uuid, created_at=now, updated_at=now)
        db.add(review)
    review.summary_text = product.summary
    review.summary_status = "approved" if req.approved else "rejected"
    review.approved_by = admin.username if req.approved else None
    review.approved_at = now if req.approved else None
    review.rejected_reason = None if req.approved else req.reason
    review.updated_at = now

    if req.approved:
        candidate = ReportCandidate(
            uuid=uuid,
            report_date=req.report_date or date.today().isoformat(),
            included=1,
            approved_by=admin.username,
            approved_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(candidate)

    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if item:
        item.current_pool = "summary_report_pool"
        item.pool_status = "approved" if req.approved else "rejected"
        item.last_operator = admin.username
        item.updated_at = now
    db.commit()
    return ResetResponse(message="摘要审核结果已更新", affected=1)
