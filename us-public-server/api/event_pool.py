"""
全局事件池 API 路由（公开访问，无需认证）
"""
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from models.models import EventPool, get_db
from schemas.schemas import EventPoolListResponse, EventPoolItem, EventPoolStatsResponse

router = APIRouter(prefix="/api/pool", tags=["全局事件池"])


def _pool_to_item(e: EventPool) -> EventPoolItem:
    return EventPoolItem(
        event_id=e.event_id,
        sub_id=e.sub_id,
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
        first_seen=e.first_seen,
        last_seen=e.last_seen,
        fetch_count=e.fetch_count or 1,
        is_active=bool(e.is_active),
    )


@router.get("", response_model=EventPoolListResponse)
def list_pool_events(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    country: Optional[str] = None,
    severity: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    获取全局事件池列表（公开接口，无需认证）
    """
    q = db.query(EventPool)
    
    if active_only:
        q = q.filter(EventPool.is_active == 1)
    
    if category:
        q = q.filter(EventPool.category == category.upper())
    if country:
        q = q.filter(EventPool.country.ilike(f"%{country}%"))
    if severity:
        q = q.filter(EventPool.severity == severity.lower())

    total = q.count()
    events = q.order_by(EventPool.last_seen.desc()).offset((page - 1) * limit).limit(limit).all()

    return EventPoolListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total else 0,
        data=[_pool_to_item(e) for e in events],
    )


@router.get("/stats", response_model=EventPoolStatsResponse)
def get_pool_stats(db: Session = Depends(get_db)):
    """
    获取全局事件池统计信息（公开接口，无需认证）
    """
    from core.event_pool_manager import EventPoolManager
    
    epm = EventPoolManager(db)
    stats = epm.get_pool_stats()
    
    return EventPoolStatsResponse(**stats)


@router.get("/{event_id}/{sub_id}")
def get_pool_event(
    event_id: int,
    sub_id: int = 0,
    db: Session = Depends(get_db),
):
    """
    获取单个事件详情（公开接口，无需认证）
    """
    event = (
        db.query(EventPool)
        .filter(
            EventPool.event_id == event_id,
            EventPool.sub_id == sub_id
        )
        .first()
    )
    
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")
    
    return _pool_to_item(event)
