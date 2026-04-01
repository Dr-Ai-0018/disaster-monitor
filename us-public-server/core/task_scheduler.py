"""
定时任务调度器（APScheduler）
"""
import uuid
import json
from datetime import datetime, timezone, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings
from utils.logger import get_logger

PROCESS_PENDING_LIMIT = 5
PROCESS_GEE_LIMIT = 5
PROCESS_ASSESS_LIMIT = 5
PROCESS_ENQUEUE_LIMIT = 5
PROCESS_INFERENCE_LIMIT = 3

logger = get_logger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


# ── 任务函数 ──────────────────────────────────────────

def job_fetch_rsoe():
    """抓取 RSOE 数据并写入数据库和全局事件池"""
    logger.info("⏰ [定时] 开始抓取 RSOE 数据...")
    from core.rsoe_spider import RsoeSpider
    from core.event_pool_manager import EventPoolManager
    from models.models import Event, get_session_factory
    from datetime import timezone

    spider = RsoeSpider()
    events_raw = spider.fetch_event_list()
    if not events_raw:
        logger.error("RSOE 抓取失败")
        return

    SessionLocal = get_session_factory()
    db = SessionLocal()
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    new_count = 0

    try:
        # 1. 先同步到全局事件池（去重）
        pool_mgr = EventPoolManager(db)
        pool_stats = pool_mgr.sync_events_to_pool(events_raw)
        logger.info(f"事件池更新: {pool_stats}")

        # 2. 再写入Events表（用于处理流程）
        for ev in events_raw:
            existing = db.query(Event).filter(
                Event.event_id == ev["event_id"],
                Event.sub_id == ev.get("sub_id", 0),
            ).first()

            if existing:
                # 增量更新：仅更新 last_update 和 severity
                if ev.get("last_update") and ev["last_update"] != existing.last_update:
                    existing.last_update = ev["last_update"]
                    existing.updated_at = now
                if ev.get("severity") and ev["severity"] != existing.severity:
                    existing.severity = ev["severity"]
                    existing.updated_at = now
                if ev.get("title"):
                    existing.title = ev["title"]
                if ev.get("category"):
                    existing.category = ev["category"]
                if ev.get("category_name"):
                    existing.category_name = ev["category_name"]
                if ev.get("country"):
                    existing.country = ev["country"]
                if ev.get("continent"):
                    existing.continent = ev["continent"]
                if ev.get("source_url"):
                    existing.source_url = ev["source_url"]
                if ev.get("event_date"):
                    existing.event_date = ev["event_date"]
                if ev.get("longitude") is not None:
                    existing.longitude = ev["longitude"]
                if ev.get("latitude") is not None:
                    existing.latitude = ev["latitude"]
                continue

            event = Event(
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
            db.add(event)
            new_count += 1

        db.commit()
        logger.info(f"RSOE 抓取完成: 新增 {new_count} 个事件到处理队列，共 {len(events_raw)} 个")
    except Exception as e:
        db.rollback()
        logger.error(f"RSOE 数据写入失败: {e}")
    finally:
        db.close()


def job_process_pool():
    """推进蓄水池：pending→pool→checked→queued"""
    logger.info("⏰ [定时] 处理蓄水池...")
    from core.pool_manager import PoolManager
    from core.event_pool_manager import EventPoolManager
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        pm = PoolManager(db)
        p1 = pm.process_pending_events(limit=PROCESS_PENDING_LIMIT)
        p2 = pm.submit_gee_tasks_for_pool(limit=PROCESS_GEE_LIMIT)
        p3 = pm.assess_ready_events(limit=PROCESS_ASSESS_LIMIT)
        p4 = pm.enqueue_checked_events(limit=PROCESS_ENQUEUE_LIMIT)
        logger.info(f"蓄水池处理完成: pending→pool={p1}, GEE任务={p2}, 质量评估={p3}, 入队={p4}")
        
        # 维护全局事件池
        epm = EventPoolManager(db)
        deactivated = epm.deactivate_stale_events(days_threshold=30)
        if deactivated > 0:
            logger.info(f"全局池维护: 标记 {deactivated} 个过期事件")
    except Exception as e:
        logger.error(f"蓄水池处理失败: {e}")
    finally:
        db.close()


def job_process_inference_queue():
    """执行内部推理队列"""
    logger.info("⏰ [定时] 执行内部推理队列...")
    from core.pool_manager import PoolManager
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        pm = PoolManager(db)
        processed = pm.process_pending_inference_tasks(limit=PROCESS_INFERENCE_LIMIT)
        logger.info(f"内部推理队列完成: {processed} 个")
    except Exception as e:
        logger.error(f"执行内部推理队列失败: {e}")
    finally:
        db.close()


def job_recheck_imagery():
    """每小时：为缺失影像的事件动态扩窗补全下载"""
    logger.info("⏰ [定时] 开始影像动态补全检查...")
    from core.pool_manager import PoolManager
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        pm = PoolManager(db)
        post_count = pm.recheck_open_imagery(limit=20)
        pre_count = pm.recheck_pre_imagery(limit=20)
        if post_count or pre_count:
            logger.info(f"影像补全: 灾后+{post_count}, 灾前+{pre_count}")
        else:
            logger.info("影像补全检查完成，暂无新增")
    except Exception as e:
        logger.error(f"影像补全检查失败: {e}")
    finally:
        db.close()


def job_generate_report():
    """生成昨日灾害日报"""
    today = date.today()
    report_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"⏰ [定时] 生成日报: {report_date}")

    from core.report_generator import ReportGenerator
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        rg = ReportGenerator()
        # 先批量生成摘要
        rg.generate_pending_summaries(db, limit=100)
        # 生成日报
        rg.generate_daily_report(db, report_date)
    except Exception as e:
        logger.error(f"日报生成失败: {e}")
    finally:
        db.close()


def job_fetch_event_details():
    """补抓新入库事件的详细信息"""
    logger.info("⏰ [定时] 开始补抓事件详情...")
    from core.event_detail_fetcher import EventDetailFetcher
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        fetcher = EventDetailFetcher(db)
        stats = fetcher.fetch_missing_details()
        logger.info(f"事件详情补抓完成: {stats}")
    except Exception as e:
        logger.error(f"事件详情补抓失败: {e}")
    finally:
        db.close()


# ── 调度器配置 ────────────────────────────────────────

def setup_scheduler():
    """注册所有定时任务"""
    sched_cfg = settings.SCHEDULER_CONFIG

    # 每 12 小时抓取 RSOE 数据（run_on_startup=true 时启动后立即执行一次）
    fetch_cfg = sched_cfg.get("fetch_rsoe_data", {})
    if fetch_cfg.get("enabled", True):
        interval_hours = fetch_cfg.get("interval_hours", 12)
        run_on_startup = fetch_cfg.get("run_on_startup", False)
        next_run = datetime.now(timezone.utc) if run_on_startup else None
        scheduler.add_job(
            job_fetch_rsoe,
            IntervalTrigger(hours=interval_hours),
            id="fetch_rsoe_data",
            replace_existing=True,
            misfire_grace_time=3600,
            next_run_time=next_run,
        )

    # 每 N 分钟补抓一次空详情事件，启动后可立即执行一次
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

    # 每小时处理蓄水池
    if sched_cfg.get("process_pool", {}).get("enabled", True):
        scheduler.add_job(
            job_process_pool,
            IntervalTrigger(hours=1),
            id="process_pool",
            replace_existing=True,
            misfire_grace_time=600,
        )

    # 每 5 分钟执行内部推理队列
    if sched_cfg.get("process_inference_queue", {}).get("enabled", True):
        scheduler.add_job(
            job_process_inference_queue,
            IntervalTrigger(
                minutes=sched_cfg.get("process_inference_queue", {}).get("interval_minutes", 5)
            ),
            id="process_inference_queue",
            replace_existing=True,
        )

    # 每小时影像动态补全
    recheck_cfg = sched_cfg.get("recheck_imagery", {})
    if recheck_cfg.get("enabled", True):
        scheduler.add_job(
            job_recheck_imagery,
            IntervalTrigger(hours=recheck_cfg.get("interval_hours", 1)),
            id="recheck_imagery",
            replace_existing=True,
            misfire_grace_time=600,
        )

    # 每天早上 7:00 生成日报
    if sched_cfg.get("generate_daily_report", {}).get("enabled", True):
        scheduler.add_job(
            job_generate_report,
            CronTrigger(hour=7, minute=0),
            id="generate_daily_report",
            replace_existing=True,
            misfire_grace_time=3600,
        )

    logger.info(f"已注册 {len(scheduler.get_jobs())} 个定时任务")
