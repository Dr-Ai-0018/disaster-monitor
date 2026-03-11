"""
成品池 API 路由
"""
import json
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.models import AdminUser, Product, get_db
from schemas.schemas import ProductListResponse, ProductSummary, ProductDetail
from utils.auth import get_current_admin

router = APIRouter(prefix="/api/products", tags=["成品池"])


def _to_summary(p: Product) -> ProductSummary:
    ir = None
    if p.inference_result:
        try:
            ir = json.loads(p.inference_result)
        except Exception:
            ir = p.inference_result
    return ProductSummary(
        uuid=p.uuid,
        event_title=p.event_title,
        event_category=p.event_category,
        event_country=p.event_country,
        inference_result=ir,
        summary=p.summary,
        summary_generated=bool(p.summary_generated),
        created_at=p.created_at,
    )


def _to_detail(p: Product) -> ProductDetail:
    ir = None
    if p.inference_result:
        try:
            ir = json.loads(p.inference_result)
        except Exception:
            ir = p.inference_result
    ed = None
    if p.event_details:
        try:
            ed = json.loads(p.event_details)
        except Exception:
            ed = p.event_details
    return ProductDetail(
        uuid=p.uuid,
        event_title=p.event_title,
        event_category=p.event_category,
        event_country=p.event_country,
        inference_result=ir,
        event_details=ed,
        summary=p.summary,
        summary_generated=bool(p.summary_generated),
        summary_generated_at=p.summary_generated_at,
        pre_image_date=p.pre_image_date,
        post_image_date=p.post_image_date,
        inference_quality_score=p.inference_quality_score,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    summary_generated: Optional[bool] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    start_date: Optional[int] = None,
    end_date: Optional[int] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    q = db.query(Product)
    if summary_generated is not None:
        q = q.filter(Product.summary_generated == (1 if summary_generated else 0))
    if category:
        q = q.filter(Product.event_category == category.upper())
    if country:
        q = q.filter(Product.event_country.ilike(f"%{country}%"))
    if start_date:
        q = q.filter(Product.created_at >= start_date)
    if end_date:
        q = q.filter(Product.created_at <= end_date)

    total = q.count()
    products = q.order_by(Product.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return ProductListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total else 0,
        data=[_to_summary(p) for p in products],
    )


@router.get("/{uuid}", response_model=ProductDetail)
def get_product(
    uuid: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    p = db.query(Product).filter(Product.uuid == uuid).first()
    if not p:
        raise HTTPException(status_code=404, detail="成品不存在")
    return _to_detail(p)
