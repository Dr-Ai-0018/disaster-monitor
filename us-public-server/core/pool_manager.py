"""
蓄水池管理模块
负责推进事件状态：pending → pool → checked → queued
"""
import uuid
import json
import time
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from config.settings import settings
from models.models import Event, GeeTask, TaskQueue
from core.gee_manager import GeeManager
from core.quality_assessor import QualityAssessor
from utils.logger import get_logger

logger = get_logger(__name__)


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _calc_priority(event: Event) -> int:
    """根据严重程度和时间计算优先级"""
    weights = settings.TASK_QUEUE_CONFIG.get("priority_weights", {})
    priority = 0
    sev_map = {
        "extreme": weights.get("severity_extreme", 100),
        "high": weights.get("severity_high", 50),
        "medium": weights.get("severity_medium", 20),
        "low": weights.get("severity_low", 10),
    }
    priority += sev_map.get(event.severity or "medium", 20)

    now_ms = _now_ms()
    if event.event_date:
        age_days = (now_ms - event.event_date) / (1000 * 86400)
        if age_days <= 7:
            priority += weights.get("recent_7d", 50)
        elif age_days <= 30:
            priority += weights.get("recent_30d", 20)

    return priority


class PoolManager:
    """蓄水池管理器"""

    def __init__(self, db: Session):
        self.db = db
        self.gee = GeeManager()
        self.qa = QualityAssessor()
        self.task_cfg = settings.TASK_QUEUE_CONFIG

    # ── 1. pending → pool（获取事件详情 + 坐标） ─────────────

    def process_pending_events(self, limit: int = 50) -> int:
        """批量处理 pending 事件，获取坐标后转为 pool"""
        from core.rsoe_spider import RsoeSpider
        spider = RsoeSpider()

        events = (
            self.db.query(Event)
            .filter(Event.status == "pending")
            .limit(limit)
            .all()
        )
        processed = 0
        for event in events:
            try:
                detail = spider.fetch_event_detail(event.event_id, event.sub_id)
                now = _now_ms()
                if detail:
                    event.longitude = detail.get("longitude")
                    event.latitude = detail.get("latitude")
                    event.continent = detail.get("continent") or event.continent
                    event.address = detail.get("address")
                    if detail.get("last_update"):
                        event.last_update = detail["last_update"]
                    event.details_json = json.dumps(detail.get("details_json", {}), ensure_ascii=False)

                if event.longitude and event.latitude:
                    event.status = "pool"
                    logger.info(f"事件 {event.event_id} 进入蓄水池 ({event.longitude:.4f}, {event.latitude:.4f})")
                else:
                    logger.warning(f"事件 {event.event_id} 无坐标，保持 pending")

                event.updated_at = now
                processed += 1
            except Exception as e:
                logger.error(f"处理事件 {event.event_id} 失败: {e}")

        self.db.commit()
        return processed

    # ── 2. pool → 提交 GEE 下载任务 ─────────────────────────

    def submit_gee_tasks_for_pool(self, limit: int = 20) -> int:
        """为蓄水池中未下载影像的事件提交 GEE 任务"""
        if self.gee.is_quota_exceeded():
            logger.warning("GEE 配额已超上限，暂停提交")
            return 0

        events = (
            self.db.query(Event)
            .filter(
                Event.status == "pool",
                Event.longitude.isnot(None),
                Event.latitude.isnot(None),
            )
            .filter(
                (Event.pre_image_downloaded == 0) | (Event.post_image_downloaded == 0)
            )
            .limit(limit)
            .all()
        )

        submitted = 0
        for event in events:
            now = _now_ms()
            event_ts = event.event_date or now

            if not event.pre_image_downloaded:
                self._submit_single_gee_task(event, event_ts, "pre_disaster")
            if not event.post_image_downloaded:
                self._submit_single_gee_task(event, event_ts, "post_disaster")

            event.updated_at = now
            submitted += 1

        self.db.commit()
        return submitted

    def _submit_single_gee_task(self, event: Event, event_ts: int, task_type: str):
        """提交单个 GEE 任务并记录到 gee_tasks 表"""
        existing = (
            self.db.query(GeeTask)
            .filter(
                GeeTask.uuid == event.uuid,
                GeeTask.task_type == task_type,
                GeeTask.status.in_(["PENDING", "RUNNING"]),
            )
            .first()
        )
        if existing:
            return

        now = _now_ms()
        gee_task = GeeTask(
            uuid=event.uuid,
            task_type=task_type,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        self.db.add(gee_task)
        self.db.flush()

        # 调用 GEE 实际下载（同步）
        result_str = self.gee.submit_download_task(
            event_uuid=event.uuid,
            longitude=event.longitude,
            latitude=event.latitude,
            event_timestamp_ms=event_ts,
            task_type=task_type,
        )

        if result_str:
            result = json.loads(result_str)
            gee_task.task_id = result.get("task_id")
            gee_task.status = "COMPLETED"
            gee_task.completed_at = _now_ms()
            gee_task.image_date = result.get("image_date_ms")
            gee_task.image_source = result.get("source")

            if task_type == "pre_disaster":
                event.pre_image_downloaded = 1
                event.pre_image_path = result.get("save_path")
                event.pre_image_date = result.get("image_date_ms")
                event.pre_image_source = result.get("source")
            else:
                event.post_image_downloaded = 1
                event.post_image_path = result.get("save_path")
                event.post_image_date = result.get("image_date_ms")
                event.post_image_source = result.get("source")

            logger.info(f"[{event.uuid[:8]}] {task_type} 下载完成")
        else:
            gee_task.status = "FAILED"
            gee_task.failure_reason = "GEE 返回空结果"
            logger.warning(f"[{event.uuid[:8]}] {task_type} 下载失败")

        gee_task.updated_at = _now_ms()

    # ── 3. pool (有双影像) → checked（质量评估） ─────────────

    def assess_ready_events(self, limit: int = 20) -> int:
        """对已有双影像的 pool 事件进行质量评估"""
        events = (
            self.db.query(Event)
            .filter(
                Event.status == "pool",
                Event.pre_image_downloaded == 1,
                Event.post_image_downloaded == 1,
                Event.quality_checked == 0,
            )
            .limit(limit)
            .all()
        )

        assessed = 0
        for event in events:
            try:
                result = self.qa.assess_pair(event.pre_image_path, event.post_image_path)
                now = _now_ms()
                event.quality_score = result.get("score", 0)
                event.quality_assessment = json.dumps(result, ensure_ascii=False)
                event.quality_checked = 1
                event.quality_pass = 1 if result.get("pass") else 0
                event.quality_check_time = now
                event.updated_at = now

                if result.get("pass"):
                    event.status = "checked"
                    logger.info(f"[{event.uuid[:8]}] 质量评估通过 (score={result['score']})")
                else:
                    logger.info(f"[{event.uuid[:8]}] 质量评估未通过 (score={result['score']})")

                assessed += 1
            except Exception as e:
                logger.error(f"质量评估异常 {event.uuid}: {e}")

        self.db.commit()
        return assessed

    # ── 4. checked → queued（加入任务队列） ──────────────────

    def enqueue_checked_events(self, limit: int = 50) -> int:
        """将 checked 事件加入 GPU 任务队列"""
        from pathlib import Path

        events = (
            self.db.query(Event)
            .filter(Event.status == "checked")
            .limit(limit)
            .all()
        )

        enqueued = 0
        for event in events:
            # 检查是否已有队列条目
            existing = self.db.query(TaskQueue).filter(TaskQueue.uuid == event.uuid).first()
            if existing:
                event.status = "queued"
                event.updated_at = _now_ms()
                continue

            try:
                task_data = self._build_task_data(event)
                priority = _calc_priority(event)
                now = _now_ms()

                task = TaskQueue(
                    uuid=event.uuid,
                    task_data=json.dumps(task_data, ensure_ascii=False),
                    priority=priority,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(task)

                event.status = "queued"
                event.updated_at = now
                enqueued += 1
                logger.info(f"[{event.uuid[:8]}] 加入任务队列 (priority={priority})")

            except Exception as e:
                logger.error(f"入队失败 {event.uuid}: {e}")

        self.db.commit()
        return enqueued

    def _build_task_data(self, event: Event) -> dict:
        """构建 GPU Worker 需要的任务数据"""
        from config.settings import settings as cfg

        server_host = f"http://localhost:{cfg.SERVER_PORT}"
        if cfg.APP_ENV == "production":
            server_host = cfg.CORS_ORIGINS[0] if cfg.CORS_ORIGINS else server_host

        task_definitions = self.task_cfg.get("tasks", [])

        details = {}
        if event.details_json:
            try:
                details = json.loads(event.details_json)
            except Exception:
                pass

        return {
            "uuid": event.uuid,
            "pre_image_url": f"{server_host}/storage/images/{event.uuid}/pre_disaster.tif",
            "post_image_url": f"{server_host}/storage/images/{event.uuid}/post_disaster.tif",
            "event_details": {
                "title": event.title,
                "category": event.category,
                "category_name": event.category_name,
                "country": event.country,
                "severity": event.severity,
                "longitude": event.longitude,
                "latitude": event.latitude,
                "event_date": event.event_date,
                "details": details,
            },
            "tasks": task_definitions,
        }

    # ── 5. 释放超时锁 ─────────────────────────────────────

    def release_timeout_locks(self) -> int:
        """释放超时的任务锁，将 locked 任务重置为 pending"""
        now = _now_ms()
        locked_tasks = (
            self.db.query(TaskQueue)
            .filter(
                TaskQueue.status == "locked",
                TaskQueue.locked_until < now,
            )
            .all()
        )

        released = 0
        for task in locked_tasks:
            if task.retry_count >= (task.max_retries or 3):
                task.status = "failed"
                task.failure_reason = "超过最大重试次数"
                # 将 event 状态回退到 checked
                event = self.db.query(Event).filter(Event.uuid == task.uuid).first()
                if event:
                    event.status = "checked"
            else:
                task.status = "pending"
                task.locked_by = None
                task.locked_at = None
                task.locked_until = None
                task.heartbeat = None
                task.retry_count = (task.retry_count or 0) + 1

            task.updated_at = now
            released += 1

        self.db.commit()
        logger.info(f"释放了 {released} 个超时锁")
        return released
