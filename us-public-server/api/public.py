"""
公开访问 API（无需认证）
- 已发布日报
- AI 分析成品
- 卫星影像缩略图
"""
import io
import json
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from models.models import DailyReport, Product, Event, get_db
from utils.logger import get_logger

router = APIRouter(prefix="/api/public", tags=["公开访问"])
logger = get_logger(__name__)


# ── 日报 ──────────────────────────────────────────────

@router.get("/reports")
def list_published_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """已发布的日报列表（公开，无需认证）"""
    q = db.query(DailyReport).filter(DailyReport.published == 1)
    total = q.count()
    reports = (
        q.order_by(DailyReport.report_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit) if total else 0,
        "data": [
            {
                "report_date": r.report_date,
                "report_title": r.report_title,
                "event_count": r.event_count or 0,
                "generated_at": r.generated_at,
                "published_at": r.published_at,
            }
            for r in reports
        ],
    }


@router.get("/reports/{date}")
def get_published_report(date: str, db: Session = Depends(get_db)):
    """获取已发布日报详情（公开，无需认证）"""
    r = db.query(DailyReport).filter(
        DailyReport.report_date == date,
        DailyReport.published == 1,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="报告不存在或未发布")

    cat = sev = cou = None
    try:
        if r.category_stats:
            cat = json.loads(r.category_stats)
        if r.severity_stats:
            sev = json.loads(r.severity_stats)
        if r.country_stats:
            cou = json.loads(r.country_stats)
    except Exception:
        pass

    return {
        "report_date": r.report_date,
        "report_title": r.report_title,
        "report_content": r.report_content,
        "event_count": r.event_count or 0,
        "category_stats": cat,
        "severity_stats": sev,
        "country_stats": cou,
        "generated_at": r.generated_at,
        "generation_time_seconds": r.generation_time_seconds,
    }


# ── AI 分析成品 ────────────────────────────────────────

@router.get("/products")
def list_public_products(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """AI 分析成品列表（公开，无需认证）"""
    total = db.query(Product).count()
    products = (
        db.query(Product)
        .order_by(Product.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = []
    for p in products:
        ir = None
        try:
            if p.inference_result:
                ir = json.loads(p.inference_result)
        except Exception:
            pass

        event = db.query(Event).filter(Event.uuid == p.uuid).first()
        items.append({
            "uuid": p.uuid,
            "event_title": p.event_title,
            "event_category": p.event_category,
            "event_country": p.event_country,
            "severity": event.severity if event else None,
            "event_date": event.event_date if event else None,
            "pre_image_date": p.pre_image_date,
            "post_image_date": p.post_image_date,
            "inference_result": ir,
            "summary": p.summary,
            "summary_generated": bool(p.summary_generated),
            "created_at": p.created_at,
            "source_url": event.source_url if event else None,
            "has_pre_image": bool(event and event.pre_image_path),
            "has_post_image": bool(event and event.post_image_path),
        })

    return {
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit) if total else 0,
        "data": items,
    }


@router.get("/products/{uuid}")
def get_public_product(uuid: str, db: Session = Depends(get_db)):
    """获取单个成品详情（公开，无需认证）"""
    p = db.query(Product).filter(Product.uuid == uuid).first()
    if not p:
        raise HTTPException(status_code=404, detail="成品不存在")

    event = db.query(Event).filter(Event.uuid == uuid).first()

    ir = ed = None
    try:
        if p.inference_result:
            ir = json.loads(p.inference_result)
        if p.event_details:
            ed = json.loads(p.event_details)
    except Exception:
        pass

    return {
        "uuid": p.uuid,
        "event_title": p.event_title,
        "event_category": p.event_category,
        "event_country": p.event_country,
        "severity": event.severity if event else None,
        "longitude": event.longitude if event else None,
        "latitude": event.latitude if event else None,
        "event_date": event.event_date if event else None,
        "address": event.address if event else None,
        "source_url": event.source_url if event else None,
        "inference_result": ir,
        "event_details": ed,
        "summary": p.summary,
        "summary_generated": bool(p.summary_generated),
        "pre_image_date": p.pre_image_date,
        "post_image_date": p.post_image_date,
        "created_at": p.created_at,
        "has_pre_image": bool(event and event.pre_image_path),
        "has_post_image": bool(event and event.post_image_path),
    }


# ── 卫星影像 PNG 缩略图 ────────────────────────────────

@router.get("/image/{uuid}/{image_type}")
def get_satellite_image(
    uuid: str,
    image_type: str,
    db: Session = Depends(get_db),
):
    """
    将 GeoTIFF 卫星影像转为 PNG 缩略图返回（公开，无需认证）
    image_type: "pre" | "post"
    """
    if image_type not in ("pre", "post"):
        raise HTTPException(status_code=400, detail="image_type 必须是 pre 或 post")

    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    image_path_str = event.pre_image_path if image_type == "pre" else event.post_image_path
    if not image_path_str:
        raise HTTPException(status_code=404, detail="影像不存在")

    from pathlib import Path
    path = Path(image_path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="影像文件不存在")

    try:
        from PIL import Image
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((900, 900))
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except ImportError:
        # Pillow 未安装，直接返回原始 TIF 字节
        return Response(
            content=path.read_bytes(),
            media_type="image/tiff",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        logger.exception(f"影像转换失败 uuid={uuid} image_type={image_type} path={path}: {e}")
        raise HTTPException(status_code=500, detail="影像转换失败")


@router.get("/image/{uuid}/{image_type}/enhanced")
def get_satellite_image_enhanced(
    uuid: str,
    image_type: str,
    db: Session = Depends(get_db),
):
    """
    返回 2%-98% 百分位拉伸增强后的 PNG（公开，无需认证）
    image_type: "pre" | "post"
    """
    if image_type not in ("pre", "post"):
        raise HTTPException(status_code=400, detail="image_type 必须是 pre 或 post")

    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    image_path_str = event.pre_image_path if image_type == "pre" else event.post_image_path
    if not image_path_str:
        raise HTTPException(status_code=404, detail="影像不存在")

    from pathlib import Path
    path = Path(image_path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="影像文件不存在")

    try:
        import numpy as np
    except Exception as e:
        logger.exception(f"增强影像依赖加载失败（numpy） uuid={uuid} image_type={image_type}: {e}")
        raise HTTPException(status_code=501, detail="增强影像依赖加载失败")

    try:
        from PIL import Image
    except Exception as e:
        logger.exception(f"增强影像依赖加载失败（Pillow） uuid={uuid} image_type={image_type}: {e}")
        raise HTTPException(status_code=501, detail="增强影像依赖加载失败")

    try:
        with Image.open(path) as img:
            arr = np.array(img.convert("RGB")).astype(np.float32)

        result = np.zeros_like(arr)
        for i in range(3):
            ch = arr[:, :, i]
            nonzero = ch[ch > 0]
            if nonzero.size == 0:
                result[:, :, i] = ch
                continue
            p2, p98 = np.percentile(nonzero, (2, 98))
            result[:, :, i] = np.clip((ch - p2) / (p98 - p2 + 1e-6) * 255, 0, 255)

        enhanced = Image.fromarray(result.astype(np.uint8))
        enhanced.thumbnail((900, 900))
        buf = io.BytesIO()
        enhanced.save(buf, format="PNG", optimize=True)
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        logger.exception(f"增强影像处理失败 uuid={uuid} image_type={image_type} path={path}: {e}")
        raise HTTPException(status_code=500, detail="影像增强失败")
