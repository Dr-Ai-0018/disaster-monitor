"""
定时任务调度器（APScheduler）
"""
import uuid
import json
from datetime import datetime, timezone, date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


# ── 任务函数 ──────────────────────────────────────────

def job_fetch_rsoe():
    """抓取 RSOE 数据并写入数据库"""
    logger.info("⏰ [定时] 开始抓取 RSOE 数据...")
    from core.rsoe_spider import RsoeSpider
    from models.models import Event, get_session_factory
    from datetime import timezone

    spider = RsoeSpider()
    html_path = spider.fetch_event_list()
    if not html_path:
        logger.error("RSOE 抓取失败")
        return

    events_raw = spider.parse_event_list(html_path)
    if not events_raw:
        logger.warning("解析到 0 个事件")
        return

    SessionLocal = get_session_factory()
    db = SessionLocal()
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    new_count = 0

    try:
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
                continue

            event = Event(
                uuid=str(uuid.uuid4()),
                event_id=ev["event_id"],
                sub_id=ev.get("sub_id", 0),
                title=ev["title"],
                category=ev.get("category"),
                category_name=ev.get("category_name"),
                country=ev.get("country"),
                severity=ev.get("severity", "medium"),
                event_date=ev.get("event_date"),
                last_update=ev.get("last_update"),
                source_url=ev.get("source_url"),
                status="pending",
                created_at=now,
                updated_at=now,
            )
            db.add(event)
            new_count += 1

        db.commit()
        logger.info(f"RSOE 抓取完成: 新增 {new_count} 个事件，共 {len(events_raw)} 个")
    except Exception as e:
        db.rollback()
        logger.error(f"RSOE 数据写入失败: {e}")
    finally:
        db.close()


def job_process_pool():
    """推进蓄水池：pending→pool→checked→queued"""
    logger.info("⏰ [定时] 处理蓄水池...")
    from core.pool_manager import PoolManager
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        pm = PoolManager(db)
        p1 = pm.process_pending_events(limit=30)
        p2 = pm.submit_gee_tasks_for_pool(limit=20)
        p3 = pm.assess_ready_events(limit=20)
        p4 = pm.enqueue_checked_events(limit=50)
        logger.info(f"蓄水池处理完成: pending→pool={p1}, GEE任务={p2}, 质量评估={p3}, 入队={p4}")
    except Exception as e:
        logger.error(f"蓄水池处理失败: {e}")
    finally:
        db.close()


def job_release_locks():
    """释放超时的任务锁"""
    logger.info("⏰ [定时] 释放超时锁...")
    from core.pool_manager import PoolManager
    from models.models import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        pm = PoolManager(db)
        released = pm.release_timeout_locks()
        logger.info(f"释放超时锁: {released} 个")
    except Exception as e:
        logger.error(f"释放超时锁失败: {e}")
    finally:
        db.close()


def job_generate_report():
    """生成昨日灾害日报"""
    from datetime import timedelta
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


# ── 调度器配置 ────────────────────────────────────────

def setup_scheduler():
    """注册所有定时任务"""
    sched_cfg = settings.SCHEDULER_CONFIG

    # 每天凌晨 2:00 抓取 RSOE 数据
    if sched_cfg.get("fetch_rsoe_data", {}).get("enabled", True):
        scheduler.add_job(
            job_fetch_rsoe,
            CronTrigger(hour=2, minute=0),
            id="fetch_rsoe_data",
            replace_existing=True,
            misfire_grace_time=3600,
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

    # 每 10 分钟释放超时锁
    if sched_cfg.get("release_timeout_locks", {}).get("enabled", True):
        scheduler.add_job(
            job_release_locks,
            IntervalTrigger(minutes=10),
            id="release_timeout_locks",
            replace_existing=True,
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
