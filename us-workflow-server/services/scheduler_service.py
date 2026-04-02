from __future__ import annotations

import uuid
from datetime import datetime, timezone

from config.settings import settings
from models.models import Event, get_session_factory
from services.event_detail_fetcher import EventDetailFetcher
from services.rsoe_spider import RsoeSpider
from services.workflow_service import mark_projection_dirty
from utils.logger import get_logger

logger = get_logger(__name__)

_scheduler = None


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def job_fetch_rsoe() -> None:
    logger.info("⏰ [workflow] 开始抓取 RSOE 数据...")
    spider = RsoeSpider()
    events_raw = spider.fetch_event_list()
    if not events_raw:
        logger.warning("[workflow] RSOE 抓取为空")
        return

    SessionLocal = get_session_factory()
    db = SessionLocal()
    now = _now_ms()
    new_count = 0
    updated_count = 0
    try:
        for ev in events_raw:
            existing = (
                db.query(Event)
                .filter(Event.event_id == ev["event_id"], Event.sub_id == ev.get("sub_id", 0))
                .first()
            )
            if existing:
                needs_detail_refresh = not bool(existing.details_json)
                if ev.get("last_update") and ev["last_update"] != existing.last_update:
                    existing.last_update = ev["last_update"]
                    existing.updated_at = now
                    needs_detail_refresh = True
                if ev.get("severity") and ev["severity"] != existing.severity:
                    existing.severity = ev["severity"]
                    existing.updated_at = now
                for field in ("title", "category", "category_name", "country", "continent", "source_url", "event_date"):
                    if ev.get(field):
                        setattr(existing, field, ev[field])
                if ev.get("longitude") is not None:
                    existing.longitude = ev["longitude"]
                if ev.get("latitude") is not None:
                    existing.latitude = ev["latitude"]
                if needs_detail_refresh:
                    existing.detail_fetch_status = "pending"
                    existing.detail_fetch_error = None
                updated_count += 1
                continue

            db.add(
                Event(
                    uuid=str(uuid.uuid4()),
                    event_id=ev["event_id"],
                    sub_id=ev.get("sub_id", 0),
                    title=ev["title"],
                    category=ev.get("category"),
                    category_name=ev.get("category_name"),
                    country=ev.get("country"),
                    continent=ev.get("continent"),
                    severity=ev.get("severity", "medium"),
                    longitude=ev.get("longitude"),
                    latitude=ev.get("latitude"),
                    event_date=ev.get("event_date"),
                    last_update=ev.get("last_update"),
                    detail_fetch_status="pending",
                    detail_fetch_attempts=0,
                    source_url=ev.get("source_url"),
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
            )
            new_count += 1
        db.commit()
        mark_projection_dirty()
        logger.info(f"[workflow] RSOE 抓取完成: 新增 {new_count}，更新 {updated_count}，总返回 {len(events_raw)}")
    except Exception as e:
        db.rollback()
        logger.error(f"[workflow] RSOE 抓取写库失败: {e}")
    finally:
        db.close()


def job_fetch_event_details() -> None:
    logger.info("⏰ [workflow] 开始补抓事件详情...")
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        fetcher = EventDetailFetcher(db)
        stats = fetcher.fetch_missing_details()
        mark_projection_dirty()
        logger.info(f"[workflow] 事件详情补抓完成: {stats}")
    except Exception as e:
        logger.error(f"[workflow] 事件详情补抓失败: {e}")
    finally:
        db.close()


def setup_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except Exception as e:
        logger.error(f"APScheduler 不可用，跳过 workflow 调度器: {e}")
        return None

    scheduler = BackgroundScheduler(timezone="UTC")
    sched_cfg = settings.SCHEDULER_CONFIG

    fetch_cfg = sched_cfg.get("fetch_rsoe_data", {})
    if fetch_cfg.get("enabled", True):
        interval_hours = fetch_cfg.get("interval_hours", 12)
        next_run = datetime.now(timezone.utc) if fetch_cfg.get("run_on_startup", False) else None
        scheduler.add_job(
            job_fetch_rsoe,
            IntervalTrigger(hours=interval_hours),
            id="fetch_rsoe_data",
            replace_existing=True,
            misfire_grace_time=3600,
            next_run_time=next_run,
        )

    if settings.DETAIL_FETCH_ENABLED:
        next_run = datetime.now(timezone.utc) if settings.DETAIL_FETCH_RUN_ON_STARTUP else None
        scheduler.add_job(
            job_fetch_event_details,
            IntervalTrigger(minutes=settings.DETAIL_FETCH_INTERVAL_MINUTES),
            id="fetch_event_details",
            replace_existing=True,
            misfire_grace_time=600,
            next_run_time=next_run,
        )

    _scheduler = scheduler
    logger.info(f"[workflow] 已注册 {len(scheduler.get_jobs())} 个定时任务")
    return scheduler


def start_scheduler() -> None:
    scheduler = setup_scheduler()
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("[workflow] 调度器已启动")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[workflow] 调度器已停止")
