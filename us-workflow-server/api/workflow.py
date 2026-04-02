from __future__ import annotations

import io
import json
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from config.settings import settings
from models.models import DailyReport, Event, ImageReview, Product, ReportCandidate, SummaryReview, TaskQueue, WorkflowItem, get_db
from schemas.schemas import (
    BatchActionResponse,
    BatchImageReviewRequest,
    BatchInferenceTriggerRequest,
    BatchPreviousPoolRollbackRequest,
    BatchStageResetRequest,
    BatchSummaryApprovalRequest,
    BatchSummaryGenerateRequest,
    BatchUuidRequest,
    ImageReviewDecisionRequest,
    InferenceTriggerRequest,
    PoolBatchActionRequest,
    ReportCandidateListResponse,
    ReportCandidateResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportDetailResponse,
    ReportSummaryListResponse,
    ReportSummaryResponse,
    ResetResponse,
    StageResetRequest,
    SummaryApprovalRequest,
    SummaryGenerateRequest,
    WorkflowBatchJobError,
    WorkflowBatchJobResponse,
    WorkflowItemDetailResponse,
    WorkflowItemListResponse,
    WorkflowItemResponse,
    WorkflowSelectionResponse,
    WorkflowOverviewCard,
    WorkflowOverviewResponse,
    BatchItemResult,
)
from services.legacy_bridge import run_legacy_action
from services.batch_job_service import create_pool_batch_job, dispatch_batch_job, get_batch_job, request_cancel_batch_job
from services.event_detail_fetcher import EventDetailFetcher
from services.scheduler_service import job_fetch_event_details, job_fetch_rsoe
from services.workflow_service import (
    ensure_workflow_item,
    latest_image_review,
    mark_projection_dirty,
    latest_report_candidate,
    reset_all_inference_stage,
    reset_inference_content,
    reset_workflow_stage,
    rollback_to_previous_pool,
    sync_workflow_projection_if_needed,
)
from utils.auth import get_current_admin

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _refresh_projection(db: Session) -> None:
    db.expire_all()
    sync_workflow_projection_if_needed(db)


def _invalidate_projection() -> None:
    mark_projection_dirty()


def _quality_label(review) -> str:
    if not review:
        return "待审核"
    mapping = {"approved": "已通过", "rejected": "已打回", "pending": "待审核"}
    return mapping.get(review.review_status or "pending", review.review_status or "待审核")


def _json_or_raw(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _summary_label(product: Product | None, summary_review: SummaryReview | None, report_candidate: ReportCandidate | None) -> str:
    if not product:
        return "无成品"
    if not product.summary:
        return "待生成摘要"
    if not summary_review:
        return "待人工审核"
    if summary_review.summary_status == "rejected":
        return "摘要已打回"
    if report_candidate:
        return "已加入日报候选"
    return "摘要已通过"


def _pool_status_label(pool_status: str) -> str:
    mapping = {
        "await_imagery": "待影像",
        "await_imagery_preparation": "待重新准备影像",
        "imagery_ready_pending_quality": "待质检归档",
        "await_image_review": "待影像审核",
        "image_rejected": "影像已打回",
        "await_inference_trigger": "待触发推理",
        "await_inference_execution": "待执行推理",
        "inference_running": "推理中",
        "inference_needs_attention": "推理需处理",
        "await_product_materialization": "待落成品",
        "await_summary_generation": "待生成摘要",
        "await_summary_review": "待摘要审核",
        "summary_rejected": "摘要已打回",
        "await_report_push": "待推入日报",
        "ready_for_daily_report": "可生成日报",
        "report_draft_ready": "日报草稿已生成",
        "report_published": "日报已发布",
    }
    return mapping.get(pool_status, pool_status)


def _get_bundle(db: Session, uuid: str):
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        return None
    task = db.query(TaskQueue).filter(TaskQueue.uuid == uuid).first()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    image_review = latest_image_review(db, uuid)
    summary_review = db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first()
    report_candidate = latest_report_candidate(db, uuid)
    daily_report = None
    if report_candidate:
        daily_report = db.query(DailyReport).filter(DailyReport.report_date == report_candidate.report_date).first()
    workflow_item = ensure_workflow_item(db, event)
    return {
        "event": event,
        "task": task,
        "product": product,
        "image_review": image_review,
        "summary_review": summary_review,
        "report_candidate": report_candidate,
        "daily_report": daily_report,
        "workflow_item": workflow_item,
    }


def _require_event_exists(db: Session, uuid: str) -> Event:
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"事件不存在: {uuid}")
    return event


def _batch_response(message: str, results: list[BatchItemResult]) -> BatchActionResponse:
    succeeded = sum(1 for item in results if item.ok)
    failed = len(results) - succeeded
    return BatchActionResponse(
        message=message,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


def _item_payload(db: Session, event: Event) -> WorkflowItemResponse:
    bundle = _get_bundle(db, event.uuid)
    assert bundle is not None
    item = bundle["workflow_item"]
    image_review = bundle["image_review"]
    product = bundle["product"]
    summary_review = bundle["summary_review"]
    report_candidate = bundle["report_candidate"]
    task = bundle["task"]
    return WorkflowItemResponse(
        uuid=event.uuid,
        title=event.title,
        country=event.country,
        severity=event.severity,
        event_status=event.status,
        pool=item.current_pool,
        imagery="已就绪" if (event.pre_image_path or event.post_image_path) else "待下载",
        quality=_quality_label(image_review),
        inference=task.status if task else "待创建",
        summary=_summary_label(product, summary_review, report_candidate),
        report_candidate=f"已加入 {report_candidate.report_date} 日报候选" if report_candidate else "未加入日报候选",
        pool_status=_pool_status_label(item.pool_status),
        event_date=event.event_date,
        latitude=event.latitude,
        longitude=event.longitude,
        selected_image_type=item.selected_image_type,
        last_operator=item.last_operator,
        updated_at=event.updated_at,
    )


def _detail_payload(db: Session, uuid: str) -> WorkflowItemDetailResponse:
    bundle = _get_bundle(db, uuid)
    if not bundle:
        raise HTTPException(status_code=404, detail="事件不存在")
    event = bundle["event"]
    task = bundle["task"]
    product = bundle["product"]
    image_review = bundle["image_review"]
    summary_review = bundle["summary_review"]
    report_candidate = bundle["report_candidate"]
    item = bundle["workflow_item"]
    base = _item_payload(db, event)
    return WorkflowItemDetailResponse(
        **base.model_dump(),
        category=event.category_name or event.category,
        address=event.address,
        source_url=event.source_url,
        last_update=event.last_update,
        detail_fetch_status=event.detail_fetch_status,
        detail_fetch_attempts=event.detail_fetch_attempts or 0,
        detail_fetch_http_status=event.detail_fetch_http_status,
        detail_fetch_last_attempt=event.detail_fetch_last_attempt,
        detail_fetch_error=event.detail_fetch_error,
        detail_fetch_completed_at=event.detail_fetch_completed_at,
        details_json=_json_or_raw(event.details_json),
        pre_image_path=event.pre_image_path,
        pre_image_date=event.pre_image_date,
        pre_image_source=event.pre_image_source,
        post_image_path=event.post_image_path,
        post_image_date=event.post_image_date,
        post_image_source=event.post_image_source,
        quality_score=event.quality_score,
        quality_assessment=_json_or_raw(event.quality_assessment),
        task_status=task.status if task else None,
        task_progress_stage=task.progress_stage if task else None,
        task_progress_message=task.progress_message if task else None,
        task_failure_reason=(task.last_error_details or task.failure_reason) if task else None,
        summary_text=product.summary if product else None,
        summary_review_status=summary_review.summary_status if summary_review else None,
        summary_review_reason=summary_review.rejected_reason if summary_review else None,
        report_date=report_candidate.report_date if report_candidate else None,
        report_ready=item.pool_status in {"ready_for_daily_report", "report_draft_ready", "report_published"},
    )


def _resolve_image_path(image_path_str: str) -> Path:
    raw = Path(image_path_str)
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend(
            [
                (settings.PROJECT_ROOT / raw).resolve(),
                (settings.LEGACY_ROOT / raw).resolve(),
                (settings.PROJECT_ROOT.parent / raw).resolve(),
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail="影像文件不存在")


def _event_image_path(event: Event, image_type: str) -> Path:
    if image_type not in {"pre", "post"}:
        raise HTTPException(status_code=400, detail="image_type 必须是 pre 或 post")
    image_path_str = event.pre_image_path if image_type == "pre" else event.post_image_path
    if not image_path_str:
        raise HTTPException(status_code=404, detail="影像不存在")
    return _resolve_image_path(image_path_str)


def _render_image_preview(path: Path) -> Response:
    try:
        from PIL import Image
    except Exception:
        return Response(content=path.read_bytes(), media_type="image/tiff")

    try:
        with Image.open(path) as img:
            preview = img.convert("RGB")
            preview.thumbnail((1200, 1200))
            buf = io.BytesIO()
            preview.save(buf, format="PNG", optimize=True)
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"影像转换失败: {exc}") from exc


def _render_enhanced_preview(path: Path) -> Response:
    try:
        import numpy as np
        from PIL import Image
    except Exception as exc:
        raise HTTPException(status_code=501, detail=f"增强影像依赖加载失败: {exc}") from exc

    try:
        with Image.open(path) as img:
            arr = np.array(img.convert("RGB")).astype(np.float32)

        result = np.zeros_like(arr)
        for idx in range(3):
            channel = arr[:, :, idx]
            nonzero = channel[channel > 0]
            if nonzero.size == 0:
                result[:, :, idx] = channel
                continue
            p2, p98 = np.percentile(nonzero, (2, 98))
            result[:, :, idx] = np.clip((channel - p2) / (p98 - p2 + 1e-6) * 255, 0, 255)

        enhanced = Image.fromarray(result.astype("uint8"))
        enhanced.thumbnail((1200, 1200))
        buf = io.BytesIO()
        enhanced.save(buf, format="PNG", optimize=True)
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"影像增强失败: {exc}") from exc


def _upsert_summary_review(
    db: Session,
    uuid: str,
    approved: bool,
    reason: str | None,
    report_date: str | None,
    operator: str,
) -> None:
    now = _now_ms()
    product = db.query(Product).filter(Product.uuid == uuid).first()
    if not product or not product.summary:
        raise HTTPException(status_code=400, detail=f"{uuid} 当前没有可审核的摘要")

    review = db.query(SummaryReview).filter(SummaryReview.uuid == uuid).first()
    if not review:
        review = SummaryReview(uuid=uuid, created_at=now, updated_at=now)
        db.add(review)

    review.summary_text = product.summary
    review.summary_status = "approved" if approved else "rejected"
    review.approved_by = operator if approved else None
    review.approved_at = now if approved else None
    review.rejected_reason = None if approved else reason
    review.updated_at = now

    existing_candidates = db.query(ReportCandidate).filter(ReportCandidate.uuid == uuid).all()
    for candidate in existing_candidates:
        candidate.included = 1 if approved else 0
        candidate.report_date = report_date or candidate.report_date
        candidate.approved_by = operator if approved else candidate.approved_by
        candidate.approved_at = now if approved else candidate.approved_at
        candidate.updated_at = now

    if approved and not existing_candidates:
        db.add(
            ReportCandidate(
                uuid=uuid,
                report_date=report_date or date.today().isoformat(),
                included=1,
                approved_by=operator,
                approved_at=now,
                created_at=now,
                updated_at=now,
            )
        )

    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if item:
        item.current_pool = "summary_report_pool"
        item.pool_status = "ready_for_daily_report" if approved else "summary_rejected"
        item.last_operator = operator
        item.updated_at = now
        item.last_transition_at = now


def _upsert_image_review(
    db: Session,
    uuid: str,
    approved: bool,
    image_type: str | None,
    reason: str | None,
    operator: str,
) -> None:
    now = _now_ms()
    review = latest_image_review(db, uuid)
    if not review:
        review = ImageReview(
            uuid=uuid,
            selected_image_type=image_type or "post",
            review_status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(review)
    review.selected_image_type = image_type or review.selected_image_type or "post"
    review.human_decision = "approved" if approved else "rejected"
    review.review_status = "approved" if approved else "rejected"
    review.ai_reason = reason or review.ai_reason
    review.reviewed_by = operator
    review.reviewed_at = now
    review.updated_at = now

    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if item:
        item.current_pool = "inference_pool" if approved else "image_review_pool"
        item.pool_status = "await_inference_trigger" if approved else "image_rejected"
        item.selected_image_type = review.selected_image_type
        item.last_operator = operator
        item.updated_at = now
        item.last_transition_at = now


@router.get("/overview", response_model=WorkflowOverviewResponse)
def workflow_overview(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _refresh_projection(db)
    descriptions = {
        "event_pool": ("自动", "抓取事件、补坐标、补详情，自动维护总事件列表"),
        "imagery_pool": ("自动", "自动提交并跟踪 GEE 影像下载，直到可进入审核"),
        "image_review_pool": ("手动", "Grok / 人工审核影像质量，决定能否进入推理"),
        "inference_pool": ("手动", "手动选择通过项，触发 Latest Model 推理"),
        "summary_report_pool": ("手动", "手动生成摘要、审核摘要、推入日报候选并生成日报"),
    }
    counts = {
        key: total
        for key, total in db.query(WorkflowItem.current_pool, func.count(WorkflowItem.uuid)).group_by(WorkflowItem.current_pool).all()
    }
    cards = []
    for key, label in [
        ("event_pool", "事件池"),
        ("imagery_pool", "影像池"),
        ("image_review_pool", "影像审核池"),
        ("inference_pool", "推理池"),
        ("summary_report_pool", "摘要日报池"),
    ]:
        count = counts.get(key, 0)
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
        service_status="online",
        automation_scope="事件抓取与影像准备",
        review_scope="审核、推理、摘要、日报",
    )


def _pool_label(pool: str) -> str:
    mapping = {
        "event_pool": "事件接入池",
        "imagery_pool": "影像准备池",
        "image_review_pool": "影像审核池",
        "inference_pool": "分析池",
        "summary_report_pool": "摘要池",
    }
    return mapping.get(pool, pool)


def _batch_job_payload(job) -> WorkflowBatchJobResponse:
    errors: list[WorkflowBatchJobError] = []
    if job.result_json:
        import json

        try:
            payload = json.loads(job.result_json)
        except json.JSONDecodeError:
            payload = {}
        for item in payload.get("errors") or []:
            if isinstance(item, dict) and item.get("uuid") and item.get("message"):
                errors.append(WorkflowBatchJobError(uuid=item["uuid"], message=item["message"]))

    return WorkflowBatchJobResponse(
        id=job.id,
        action=job.action,
        target_pool=job.target_pool,
        status=job.status,
        progress_total=job.progress_total,
        progress_completed=job.progress_completed,
        progress_succeeded=job.progress_succeeded,
        progress_failed=job.progress_failed,
        progress_message=job.progress_message,
        cancel_requested=bool(job.cancel_requested),
        error_message=job.error_message,
        created_by=job.created_by,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        updated_at=job.updated_at,
        errors=errors,
    )


def _latest_by_uuid(rows):
    result = {}
    for row in rows:
        result.setdefault(row.uuid, row)
    return result


def _load_related_maps(db: Session, uuids: list[str]):
    if not uuids:
        return {
            "workflow_items": {},
            "tasks": {},
            "products": {},
            "summary_reviews": {},
            "image_reviews": {},
            "report_candidates": {},
            "daily_reports": {},
        }

    workflow_items = {row.uuid: row for row in db.query(WorkflowItem).filter(WorkflowItem.uuid.in_(uuids)).all()}
    tasks = {row.uuid: row for row in db.query(TaskQueue).filter(TaskQueue.uuid.in_(uuids)).all()}
    products = {row.uuid: row for row in db.query(Product).filter(Product.uuid.in_(uuids)).all()}
    summary_reviews = {row.uuid: row for row in db.query(SummaryReview).filter(SummaryReview.uuid.in_(uuids)).all()}
    image_reviews = _latest_by_uuid(
        db.query(ImageReview)
        .filter(ImageReview.uuid.in_(uuids))
        .order_by(ImageReview.uuid.asc(), ImageReview.updated_at.desc(), ImageReview.id.desc())
        .all()
    )
    report_candidates = _latest_by_uuid(
        db.query(ReportCandidate)
        .filter(ReportCandidate.uuid.in_(uuids), ReportCandidate.included == 1)
        .order_by(ReportCandidate.uuid.asc(), ReportCandidate.updated_at.desc(), ReportCandidate.id.desc())
        .all()
    )
    report_dates = {row.report_date for row in report_candidates.values()}
    daily_reports = {}
    if report_dates:
        daily_reports = {
            row.report_date: row
            for row in db.query(DailyReport).filter(DailyReport.report_date.in_(report_dates)).all()
        }

    return {
        "workflow_items": workflow_items,
        "tasks": tasks,
        "products": products,
        "summary_reviews": summary_reviews,
        "image_reviews": image_reviews,
        "report_candidates": report_candidates,
        "daily_reports": daily_reports,
    }


def _item_payload_from_maps(db: Session, event: Event, related_maps) -> WorkflowItemResponse:
    item = related_maps["workflow_items"].get(event.uuid) or ensure_workflow_item(db, event)
    image_review = related_maps["image_reviews"].get(event.uuid)
    product = related_maps["products"].get(event.uuid)
    summary_review = related_maps["summary_reviews"].get(event.uuid)
    report_candidate = related_maps["report_candidates"].get(event.uuid)
    task = related_maps["tasks"].get(event.uuid)
    return WorkflowItemResponse(
        uuid=event.uuid,
        title=event.title,
        country=event.country,
        severity=event.severity,
        event_status=event.status,
        pool=item.current_pool,
        imagery="已就绪" if (event.pre_image_path or event.post_image_path) else "待下载",
        quality=_quality_label(image_review),
        inference=task.status if task else "待创建",
        summary=_summary_label(product, summary_review, report_candidate),
        report_candidate=f"已加入 {report_candidate.report_date} 日报候选" if report_candidate else "未加入日报候选",
        pool_status=_pool_status_label(item.pool_status),
        event_date=event.event_date,
        latitude=event.latitude,
        longitude=event.longitude,
        selected_image_type=item.selected_image_type,
        last_operator=item.last_operator,
        updated_at=event.updated_at,
    )


@router.get("/items", response_model=WorkflowItemListResponse)
def list_workflow_items(
    pool: str = Query("event_pool"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _refresh_projection(db)
    query = (
        db.query(Event)
        .join(WorkflowItem, WorkflowItem.uuid == Event.uuid)
        .filter(WorkflowItem.current_pool == pool)
        .order_by(WorkflowItem.updated_at.desc(), Event.updated_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    related_maps = _load_related_maps(db, [event.uuid for event in rows])
    return WorkflowItemListResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=[_item_payload_from_maps(db, event, related_maps) for event in rows],
    )


@router.get("/items/selection", response_model=WorkflowSelectionResponse)
def list_workflow_item_selection(
    pool: str = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _refresh_projection(db)
    uuids = [
        row[0]
        for row in (
            db.query(WorkflowItem.uuid)
            .filter(WorkflowItem.current_pool == pool)
            .order_by(WorkflowItem.updated_at.desc(), WorkflowItem.uuid.asc())
            .all()
        )
    ]
    return WorkflowSelectionResponse(total=len(uuids), uuids=uuids)


@router.post("/pool-actions", response_model=WorkflowBatchJobResponse)
def create_pool_action_job(
    req: PoolBatchActionRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if req.action not in {"rollback_previous", "rollback_reaudit"}:
        raise HTTPException(status_code=400, detail=f"不支持的池子动作: {req.action}")
    if req.pool not in {"imagery_pool", "image_review_pool", "inference_pool", "summary_report_pool"}:
        raise HTTPException(status_code=400, detail=f"不支持的池子: {req.pool}")
    if req.action == "rollback_reaudit" and req.pool not in {"inference_pool", "summary_report_pool"}:
        raise HTTPException(status_code=400, detail="一键回溯仅支持分析池和摘要池")

    _refresh_projection(db)
    try:
        job = create_pool_batch_job(db, action=req.action, target_pool=req.pool, created_by=admin.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dispatch_batch_job(job.id)
    return _batch_job_payload(job)


@router.get("/batch-jobs/{job_id}", response_model=WorkflowBatchJobResponse)
def get_workflow_batch_job(
    job_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    job = get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"批量任务不存在: {job_id}")
    return _batch_job_payload(job)


@router.post("/batch-jobs/{job_id}/cancel", response_model=WorkflowBatchJobResponse)
def cancel_workflow_batch_job(
    job_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    job = request_cancel_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"批量任务不存在: {job_id}")
    return _batch_job_payload(job)


@router.get("/items/{uuid}", response_model=WorkflowItemDetailResponse)
def get_workflow_item_detail(
    uuid: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _refresh_projection(db)
    return _detail_payload(db, uuid)


@router.post("/items/{uuid}/refresh-detail", response_model=ResetResponse)
def refresh_workflow_item_detail(
    uuid: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _require_event_exists(db, uuid)
    fetcher = EventDetailFetcher(db)
    try:
        result = fetcher.refresh_single_event(uuid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _invalidate_projection()
    if result.get("success"):
        return ResetResponse(message="事件详情已重新补抓", affected=1)
    raise HTTPException(
        status_code=502 if result.get("http_status") else 400,
        detail=result.get("error") or "事件详情补抓失败",
    )


@router.get("/items/{uuid}/images/{image_type}")
def get_workflow_image_preview(
    uuid: str,
    image_type: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    event = _require_event_exists(db, uuid)
    path = _event_image_path(event, image_type)
    return _render_image_preview(path)


@router.get("/items/{uuid}/images/{image_type}/enhanced")
def get_workflow_image_enhanced_preview(
    uuid: str,
    image_type: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    event = _require_event_exists(db, uuid)
    path = _event_image_path(event, image_type)
    return _render_enhanced_preview(path)


@router.post("/maintenance/fetch-rsoe", response_model=ResetResponse)
def manual_fetch_rsoe(
    _=Depends(get_current_admin),
):
    job_fetch_rsoe()
    return ResetResponse(message="已手动执行 RSOE 抓取", affected=1)


@router.post("/maintenance/fetch-event-details", response_model=ResetResponse)
def manual_fetch_event_details(
    _=Depends(get_current_admin),
):
    job_fetch_event_details()
    return ResetResponse(message="已手动执行事件详情补抓", affected=1)


@router.get("/report-candidates", response_model=ReportCandidateListResponse)
def list_report_candidates(
    report_date: str = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    rows = (
        db.query(ReportCandidate, Event)
        .join(Event, Event.uuid == ReportCandidate.uuid)
        .filter(ReportCandidate.report_date == report_date, ReportCandidate.included == 1)
        .order_by(ReportCandidate.updated_at.desc())
        .all()
    )
    data = [
        ReportCandidateResponse(
            uuid=event.uuid,
            title=event.title,
            country=event.country,
            severity=event.severity,
            report_date=candidate.report_date,
            updated_at=event.updated_at,
        )
        for candidate, event in rows
    ]
    return ReportCandidateListResponse(total=len(data), data=data)


@router.get("/reports", response_model=ReportSummaryListResponse)
def list_reports(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    rows = db.query(DailyReport).order_by(DailyReport.report_date.desc()).limit(limit).all()
    data = [
        ReportSummaryResponse(
            report_date=row.report_date,
            report_title=row.report_title,
            event_count=row.event_count or 0,
            generated_at=row.generated_at,
            published=bool(row.published),
        )
        for row in rows
    ]
    return ReportSummaryListResponse(total=len(data), data=data)


@router.get("/reports/{report_date}", response_model=ReportDetailResponse)
def get_report_detail(
    report_date: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    row = db.query(DailyReport).filter(DailyReport.report_date == report_date).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"日期 {report_date} 无日报")
    return ReportDetailResponse(
        report_date=row.report_date,
        report_title=row.report_title,
        event_count=row.event_count or 0,
        generated_at=row.generated_at,
        published=bool(row.published),
        report_content=row.report_content,
        category_stats=row.category_stats,
        severity_stats=row.severity_stats,
        country_stats=row.country_stats,
        published_at=row.published_at,
    )


@router.post("/items/{uuid}/reset-inference", response_model=ResetResponse)
def reset_item_inference(
    uuid: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    affected = reset_inference_content(db, uuid)
    if affected == 0:
        raise HTTPException(status_code=404, detail="未找到可重置的推理/摘要内容")
    _invalidate_projection()
    return ResetResponse(message="已清空成品与推理/摘要阶段内容", affected=affected)


@router.post("/items/batch-reset-inference", response_model=BatchActionResponse)
def batch_reset_inference(
    req: BatchUuidRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            affected = reset_inference_content(db, uuid)
            if affected == 0:
                results.append(BatchItemResult(uuid=uuid, ok=False, message="未找到可重置内容"))
            else:
                results.append(BatchItemResult(uuid=uuid, ok=True, message=f"已重置 {affected} 项"))
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
    _invalidate_projection()
    return _batch_response("已处理所选推理/摘要阶段重置", results)


@router.post("/items/{uuid}/reset-stage", response_model=ResetResponse)
def reset_item_stage(
    uuid: str,
    req: StageResetRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        affected = reset_workflow_stage(db, uuid, req.stage)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if affected == 0:
        raise HTTPException(status_code=404, detail="未找到可回退的内容")
    _invalidate_projection()
    return ResetResponse(message=f"已回退到 {req.stage} 阶段", affected=affected)


@router.post("/items/batch-reset-stage", response_model=BatchActionResponse)
def batch_reset_stage(
    req: BatchStageResetRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if not req.uuids:
        raise HTTPException(status_code=400, detail="请选择至少一条事件")
    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            affected = reset_workflow_stage(db, uuid, req.stage)
            if affected == 0:
                results.append(BatchItemResult(uuid=uuid, ok=False, message="未找到可回退内容"))
            else:
                results.append(BatchItemResult(uuid=uuid, ok=True, message=f"已回退到 {req.stage}"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
    _invalidate_projection()
    return _batch_response(f"已处理批量阶段回退: {req.stage}", results)


@router.post("/items/{uuid}/rollback-previous", response_model=ResetResponse)
def rollback_item_previous_pool(
    uuid: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    try:
        result = rollback_to_previous_pool(db, uuid, operator=admin.username)
    except ValueError as exc:
        detail = str(exc)
        if "不存在" in detail:
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    _invalidate_projection()
    return ResetResponse(
        message=f"已打回到{_pool_label(result['after_pool'])}",
        affected=max(1, result["affected"]),
    )


@router.post("/items/batch-rollback-previous", response_model=BatchActionResponse)
def batch_rollback_previous_pool(
    req: BatchPreviousPoolRollbackRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if not req.uuids:
        raise HTTPException(status_code=400, detail="请选择至少一条事件")

    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            result = rollback_to_previous_pool(db, uuid, operator=admin.username)
            results.append(
                BatchItemResult(
                    uuid=uuid,
                    ok=True,
                    message=f"已打回到{_pool_label(result['after_pool'])}",
                )
            )
        except ValueError as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))

    _invalidate_projection()
    return _batch_response("已处理批量上一池回退", results)


@router.post("/reset-inference-all", response_model=ResetResponse)
def reset_inference_all(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    affected = reset_all_inference_stage(db)
    _invalidate_projection()
    return ResetResponse(message="已批量重置所有推理/摘要阶段内容", affected=affected)


@router.post("/items/{uuid}/image-review", response_model=ResetResponse)
def decide_image_review(
    uuid: str,
    req: ImageReviewDecisionRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    _require_event_exists(db, uuid)
    _upsert_image_review(db, uuid, req.approved, req.image_type, req.reason, admin.username)
    db.commit()
    _invalidate_projection()
    return ResetResponse(message="影像审核结果已写入", affected=1)


@router.post("/items/batch-image-review", response_model=BatchActionResponse)
def batch_image_review(
    req: BatchImageReviewRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if not req.uuids:
        raise HTTPException(status_code=400, detail="请选择至少一条事件")
    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            _require_event_exists(db, uuid)
            _upsert_image_review(db, uuid, req.approved, req.image_type, req.reason, admin.username)
            results.append(BatchItemResult(uuid=uuid, ok=True, message="影像审核结果已写入"))
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
    db.commit()
    _invalidate_projection()
    return _batch_response("已处理批量影像审核", results)


@router.post("/items/{uuid}/trigger-inference", response_model=ResetResponse)
def trigger_inference(
    uuid: str,
    req: InferenceTriggerRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    _require_event_exists(db, uuid)
    result = run_legacy_action("trigger_inference", {"uuid": uuid, "selected_image_type": req.selected_image_type})
    _invalidate_projection()
    return ResetResponse(
        message=f"已触发推理，事件状态 {result.get('event_status') or '-'}，任务状态 {result.get('task_status') or '-'}",
        affected=1,
    )


@router.post("/items/batch-trigger-inference", response_model=BatchActionResponse)
def batch_trigger_inference(
    req: BatchInferenceTriggerRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if not req.uuids:
        raise HTTPException(status_code=400, detail="请选择至少一条事件")
    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            _require_event_exists(db, uuid)
            result = run_legacy_action("trigger_inference", {"uuid": uuid, "selected_image_type": req.selected_image_type})
            results.append(
                BatchItemResult(
                    uuid=uuid,
                    ok=True,
                    message=f"事件 {result.get('event_status') or '-'} / 任务 {result.get('task_status') or '-'}",
                )
            )
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
    _invalidate_projection()
    return _batch_response("已处理批量推理触发", results)


@router.post("/items/{uuid}/generate-summary", response_model=ResetResponse)
def generate_summary(
    uuid: str,
    req: SummaryGenerateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _require_event_exists(db, uuid)
    run_legacy_action("generate_summary", {"uuid": uuid, "persist": req.persist})
    _invalidate_projection()
    return ResetResponse(message="摘要已生成并写回数据库", affected=1)


@router.post("/items/batch-generate-summary", response_model=BatchActionResponse)
def batch_generate_summary(
    req: BatchSummaryGenerateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if not req.uuids:
        raise HTTPException(status_code=400, detail="请选择至少一条事件")
    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            _require_event_exists(db, uuid)
            run_legacy_action("generate_summary", {"uuid": uuid, "persist": req.persist})
            results.append(BatchItemResult(uuid=uuid, ok=True, message="摘要生成完成"))
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
    _invalidate_projection()
    return _batch_response("已处理批量摘要生成", results)


@router.post("/items/{uuid}/summary-approval", response_model=ResetResponse)
def approve_summary(
    uuid: str,
    req: SummaryApprovalRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    _require_event_exists(db, uuid)
    _upsert_summary_review(db, uuid, req.approved, req.reason, req.report_date, admin.username)
    db.commit()
    _invalidate_projection()
    return ResetResponse(message="摘要审核结果已更新", affected=1)


@router.post("/items/{uuid}/remove-report-candidate", response_model=ResetResponse)
def remove_report_candidate(
    uuid: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    _require_event_exists(db, uuid)
    rows = db.query(ReportCandidate).filter(ReportCandidate.uuid == uuid, ReportCandidate.included == 1).all()
    if not rows:
        raise HTTPException(status_code=404, detail="当前事件不在日报候选中")
    now = _now_ms()
    for row in rows:
        row.included = 0
        row.updated_at = now
    item = db.query(WorkflowItem).filter(WorkflowItem.uuid == uuid).first()
    if item:
        item.current_pool = "summary_report_pool"
        item.pool_status = "await_report_push"
        item.last_operator = admin.username
        item.updated_at = now
        item.last_transition_at = now
    db.commit()
    _invalidate_projection()
    return ResetResponse(message="已将事件移出日报候选", affected=len(rows))


@router.post("/items/batch-summary-approval", response_model=BatchActionResponse)
def batch_summary_approval(
    req: BatchSummaryApprovalRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if not req.uuids:
        raise HTTPException(status_code=400, detail="请选择至少一条事件")
    results: list[BatchItemResult] = []
    for uuid in req.uuids:
        try:
            _require_event_exists(db, uuid)
            _upsert_summary_review(db, uuid, req.approved, req.reason, req.report_date, admin.username)
            results.append(BatchItemResult(uuid=uuid, ok=True, message="已加入日报候选" if req.approved else "摘要已打回"))
        except Exception as exc:
            results.append(BatchItemResult(uuid=uuid, ok=False, message=str(exc)))
    db.commit()
    _invalidate_projection()
    return _batch_response("已处理批量摘要审核", results)


@router.post("/reports/generate", response_model=ReportGenerateResponse)
def generate_report(
    req: ReportGenerateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    _ = db
    result = run_legacy_action(
        "generate_candidate_report",
        {"report_date": req.report_date, "database_path": settings.DATABASE_PATH},
    )
    _invalidate_projection()
    return ReportGenerateResponse(
        message="已按日报候选池生成日报草稿",
        report_date=result["report_date"],
        report_title=result.get("report_title"),
        event_count=result.get("event_count", 0),
        published=bool(result.get("published")),
    )


@router.post("/reports/{report_date}/publish", response_model=ResetResponse)
def publish_report(
    report_date: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    report = db.query(DailyReport).filter(DailyReport.report_date == report_date).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"日期 {report_date} 无日报")
    report.published = 1
    report.published_at = _now_ms()
    db.commit()
    _invalidate_projection()
    return ResetResponse(message=f"日报 {report_date} 已发布", affected=1)
