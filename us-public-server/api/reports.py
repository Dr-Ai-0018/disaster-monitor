"""
日报管理 API 路由
"""
import json
import math
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from models.models import AdminUser, DailyReport, get_db
from schemas.schemas import (
    ReportListResponse, ReportSummary, ReportDetail,
    GenerateReportRequest, GenerateReportResponse, MessageResponse,
)
from utils.auth import get_current_admin

router = APIRouter(prefix="/api/reports", tags=["日报管理"])


def _to_summary(r: DailyReport) -> ReportSummary:
    return ReportSummary(
        id=r.id,
        report_date=r.report_date,
        report_title=r.report_title,
        event_count=r.event_count or 0,
        generated_at=r.generated_at,
        published=bool(r.published),
    )


def _to_detail(r: DailyReport) -> ReportDetail:
    cat = None
    sev = None
    cou = None
    try:
        if r.category_stats:
            cat = json.loads(r.category_stats)
        if r.severity_stats:
            sev = json.loads(r.severity_stats)
        if r.country_stats:
            cou = json.loads(r.country_stats)
    except Exception:
        pass

    return ReportDetail(
        id=r.id,
        report_date=r.report_date,
        report_title=r.report_title,
        report_content=r.report_content,
        event_count=r.event_count or 0,
        category_stats=cat,
        severity_stats=sev,
        country_stats=cou,
        generated_at=r.generated_at,
        generated_by=r.generated_by,
        generation_time_seconds=r.generation_time_seconds,
        published=bool(r.published),
        published_at=r.published_at,
    )


@router.get("", response_model=ReportListResponse)
def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    total = db.query(DailyReport).count()
    reports = (
        db.query(DailyReport)
        .order_by(DailyReport.report_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ReportListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total else 0,
        data=[_to_summary(r) for r in reports],
    )


@router.get("/{date}", response_model=ReportDetail)
def get_report(
    date: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    r = db.query(DailyReport).filter(DailyReport.report_date == date).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"日期 {date} 无日报")
    return _to_detail(r)


@router.post("/generate", response_model=GenerateReportResponse)
def generate_report(
    req: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    def _run(date: str):
        from core.report_generator import ReportGenerator
        from models.models import get_session_factory
        s = get_session_factory()()
        try:
            rg = ReportGenerator()
            rg.generate_daily_report(s, date)
        finally:
            s.close()

    background_tasks.add_task(_run, req.date)
    return GenerateReportResponse(message="日报生成任务已启动", report_date=req.date)


@router.put("/{date}/publish", response_model=MessageResponse)
def publish_report(
    date: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    from datetime import datetime, timezone
    r = db.query(DailyReport).filter(DailyReport.report_date == date).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"日期 {date} 无日报")

    r.published = 1
    r.published_at = int(datetime.now(timezone.utc).timestamp() * 1000)
    db.commit()
    return MessageResponse(message=f"日报 {date} 已发布")
