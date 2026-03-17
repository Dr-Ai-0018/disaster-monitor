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
from models.models import Event, GeeTask, TaskQueue, EventPool
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
        from core.event_pool_manager import EventPoolManager
        spider = RsoeSpider()
        epm = EventPoolManager(self.db)

        events = (
            self.db.query(Event)
            .filter(Event.status == "pending")
            .limit(limit)
            .all()
        )
        moved_to_pool = 0
        for event in events:
            try:
                now = _now_ms()
                pool_event = (
                    self.db.query(EventPool)
                    .filter(
                        EventPool.event_id == event.event_id,
                        EventPool.sub_id == event.sub_id,
                    )
                    .first()
                )

                if pool_event:
                    if event.longitude is None and pool_event.longitude is not None:
                        event.longitude = pool_event.longitude
                    if event.latitude is None and pool_event.latitude is not None:
                        event.latitude = pool_event.latitude
                    if not event.continent and pool_event.continent:
                        event.continent = pool_event.continent
                    if not event.address and pool_event.address:
                        event.address = pool_event.address
                    if not event.category_name and pool_event.category_name:
                        event.category_name = pool_event.category_name
                    if not event.country and pool_event.country:
                        event.country = pool_event.country
                    if not event.event_date and pool_event.event_date:
                        event.event_date = pool_event.event_date
                    if not event.last_update and pool_event.last_update:
                        event.last_update = pool_event.last_update

                detail = None
                if event.longitude is None or event.latitude is None:
                    detail = spider.fetch_event_detail(event.event_id, event.sub_id)

                if detail:
                    event.longitude = detail.get("longitude")
                    event.latitude = detail.get("latitude")
                    event.continent = detail.get("continent") or event.continent
                    event.address = detail.get("address")
                    event.country = detail.get("country") or event.country
                    event.category = detail.get("category") or event.category
                    event.category_name = detail.get("category_name") or event.category_name
                    event.severity = detail.get("severity") or event.severity
                    event.event_date = detail.get("event_date") or event.event_date
                    if detail.get("last_update"):
                        event.last_update = detail["last_update"]
                    event.details_json = json.dumps(detail.get("details_json", {}), ensure_ascii=False)

                    # 同步到全局事件池
                    if event.longitude and event.latitude:
                        epm.update_pool_coordinates(
                            event.event_id, event.sub_id,
                            event.longitude, event.latitude,
                            event.continent, event.address
                        )
                    if detail.get("details_json"):
                        epm.update_pool_details(event.event_id, event.sub_id, detail.get("details_json", {}))

                if event.longitude and event.latitude:
                    event.status = "pool"
                    epm.link_event_to_pool(event.uuid, event.event_id, event.sub_id)
                    logger.info(f"事件 {event.event_id} 进入蓄水池 ({event.longitude:.4f}, {event.latitude:.4f})")
                    moved_to_pool += 1
                else:
                    logger.warning(f"事件 {event.event_id} 无坐标，保持 pending")

                event.updated_at = now
            except Exception as e:
                logger.error(f"处理事件 {event.event_id} 失败: {e}")

        self.db.commit()
        return moved_to_pool

    # ── 2. pool → 提交 GEE 下载任务 ─────────────────────────

    def submit_gee_tasks_for_pool(self, limit: int = 20) -> int:
        """为蓄水池中未下载影像的事件提交 GEE 任务（使用各事件的当前窗口大小）"""
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

            if not event.pre_image_downloaded and not event.pre_imagery_exhausted:
                self._submit_single_gee_task(
                    event, event_ts, "pre_disaster",
                    window_days=event.pre_window_days or 7,
                )
            if not event.post_image_downloaded and event.post_imagery_open:
                self._submit_single_gee_task(
                    event, event_ts, "post_disaster",
                    window_days=event.post_window_days or 7,
                )

            event.updated_at = now
            submitted += 1

        self.db.commit()

        # 仅对窗口已耗尽的事件推进状态
        self._advance_no_imagery_events()

        return submitted

    def _advance_no_imagery_events(self) -> int:
        """
        将 GEE 下载永久失败（无可用卫星影像）的 pool 事件直接推进到 checked。
        若 fail_open=True：推进到 checked（最终会入队给 GPU）。
        若 fail_open=False：打 warning 日志，事件保留在 pool。
        """
        pool_events = (
            self.db.query(Event)
            .filter(Event.status == "pool")
            .all()
        )

        advanced = 0
        now = _now_ms()

        for event in pool_events:
            # 还有进行中的任务，先等
            active = (
                self.db.query(GeeTask)
                .filter(
                    GeeTask.uuid == event.uuid,
                    GeeTask.status.in_(["PENDING", "RUNNING"]),
                )
                .first()
            )
            if active:
                continue

            # 只有当两类影像都"终止搜索"后，才推进
            pre_done = event.pre_image_downloaded or event.pre_imagery_exhausted
            post_done = event.post_image_downloaded or (event.post_imagery_open == 0)
            if not (pre_done and post_done):
                continue  # 还有窗口可扩，等待 recheck 再试

            # 标记失败影像为"已尝试"（避免 assess_ready_events 处理时崩溃）
            if not event.pre_image_downloaded and event.pre_imagery_exhausted:
                event.pre_image_downloaded = 1
                event.pre_image_path = None
            if not event.post_image_downloaded and event.post_imagery_open == 0:
                event.post_image_downloaded = 1
                event.post_image_path = None

            # 直接写入质量评估结果，跳过实际图像评估
            qa = {
                "score": 0,
                "pass": self.qa.fail_open,
                "no_imagery": True,
                "reason": "GEE 未找到可用卫星影像，依据 fail_open 配置决定是否放行",
            }
            event.quality_score = 0
            event.quality_assessment = json.dumps(qa, ensure_ascii=False)
            event.quality_checked = 1
            event.quality_pass = 1 if self.qa.fail_open else 0
            event.quality_check_time = now
            event.updated_at = now

            if self.qa.fail_open:
                event.status = "checked"
                logger.info(f"[{event.uuid[:8]}] GEE 无可用影像，fail_open=True → 推进到 checked")
                advanced += 1
            else:
                logger.warning(f"[{event.uuid[:8]}] GEE 无可用影像，fail_open=False → 保留 pool")

        if advanced > 0:
            self.db.commit()
            logger.info(f"共 {advanced} 个无影像事件推进到 checked")

        return advanced

    def _submit_single_gee_task(
        self,
        event: Event,
        event_ts: int,
        task_type: str,
        window_days: int = None,
        allow_retry: bool = False,
    ):
        """
        提交单个 GEE 任务并记录到 gee_tasks 表。

        allow_retry=False（默认，正常首次提交）：PENDING/RUNNING/FAILED 均跳过，防止立即重试。
        allow_retry=True（recheck 调用）：仅跳过 PENDING/RUNNING，允许对旧的 FAILED 记录发起
        新一轮下载（以当前扩展后的窗口为准）。
        """
        skip_statuses = ["PENDING", "RUNNING"] if allow_retry else ["PENDING", "RUNNING", "FAILED"]
        existing = (
            self.db.query(GeeTask)
            .filter(
                GeeTask.uuid == event.uuid,
                GeeTask.task_type == task_type,
                GeeTask.status.in_(skip_statuses),
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
            window_days=window_days,
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
                event.pre_imagery_last_check = now
            else:
                event.post_image_downloaded = 1
                event.post_image_path = result.get("save_path")
                event.post_image_date = result.get("image_date_ms")
                event.post_image_source = result.get("source")
                event.post_imagery_open = 0
                event.post_imagery_last_check = now

            logger.info(f"[{event.uuid[:8]}] {task_type} 下载完成")
        else:
            gee_task.status = "FAILED"
            gee_task.failure_reason = "GEE 返回空结果"

            max_win = self.task_cfg.get("max_imagery_window_days",
                                        self.gee.cfg.get("max_imagery_window_days", 60))
            if task_type == "pre_disaster":
                cur = event.pre_window_days or 7
                new_win = cur + 7
                event.pre_imagery_last_check = now
                if new_win > max_win:
                    event.pre_imagery_exhausted = 1
                    logger.warning(f"[{event.uuid[:8]}] 灾前影像达到最大窗口 {max_win}d，停止搜索")
                else:
                    event.pre_window_days = new_win
                    logger.info(f"[{event.uuid[:8]}] 灾前影像未找到，窗口扩展至 {new_win}d")
            else:
                cur = event.post_window_days or 7
                new_win = cur + 7
                event.post_imagery_last_check = now
                if new_win > max_win:
                    event.post_imagery_open = 0
                    logger.warning(f"[{event.uuid[:8]}] 灾后影像达到最大窗口 {max_win}d，停止追踪")
                else:
                    event.post_window_days = new_win
                    logger.info(f"[{event.uuid[:8]}] 灾后影像未找到，窗口扩展至 {new_win}d（将在下次检查时重试）")

            logger.warning(f"[{event.uuid[:8]}] {task_type} 下载失败")

        event.imagery_check_count = (event.imagery_check_count or 0) + 1
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

        # 优先使用显式配置的 SERVER_BASE_URL（生产环境必须设置），
        # 否则回退到 localhost（仅适用于 GPU Worker 与 US Server 同机或同内网的场景）
        server_host = cfg.SERVER_BASE_URL or f"http://localhost:{cfg.SERVER_PORT}"

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

    # ── 5. 动态影像补全（灾后轮询 + 灾前扩窗） ──────────────

    def recheck_open_imagery(self, limit: int = 20) -> int:
        """
        每小时：对 post_imagery_open=1 且灾后影像未下载的事件，
        每 24h 重新尝试 GEE 下载（使用当前 post_window_days）。
        成功→记录影像路径、关闭追踪；失败→扩展窗口或关闭追踪。
        """
        recheck_interval_ms = int(
            self.gee.cfg.get("imagery_recheck_interval_hours", 24) * 3600 * 1000
        )
        now = _now_ms()
        threshold = now - recheck_interval_ms

        events = (
            self.db.query(Event)
            .filter(
                Event.status == "pool",
                Event.post_image_downloaded == 0,
                Event.post_imagery_open == 1,
                Event.longitude.isnot(None),
                Event.latitude.isnot(None),
            )
            .filter(
                (Event.post_imagery_last_check.is_(None)) |
                (Event.post_imagery_last_check < threshold)
            )
            .limit(limit)
            .all()
        )

        success = 0
        for event in events:
            try:
                event_ts = event.event_date or now
                self._submit_single_gee_task(
                    event, event_ts, "post_disaster",
                    window_days=event.post_window_days or 7,
                    allow_retry=True,  # recheck：允许越过旧 FAILED 记录重试
                )
                if event.post_image_downloaded:
                    success += 1
                    # 若灾前影像也已就绪，重置质量检查以触发评估
                    if event.pre_image_downloaded and event.quality_checked:
                        event.quality_checked = 0
                        event.quality_pass = 0
                event.updated_at = now
            except Exception as e:
                logger.error(f"[{event.uuid[:8]}] recheck post imagery 失败: {e}")

        if events:
            self.db.commit()
        return success

    def recheck_pre_imagery(self, limit: int = 20) -> int:
        """
        对灾前影像未下载且未 exhausted 的 pool 事件，自动扩窗重查。
        历史影像随时可用，无 24h 间隔限制（直到窗口耗尽或下载成功）。
        """
        events = (
            self.db.query(Event)
            .filter(
                Event.status == "pool",
                Event.pre_image_downloaded == 0,
                Event.pre_imagery_exhausted == 0,
                Event.longitude.isnot(None),
                Event.latitude.isnot(None),
            )
            .limit(limit)
            .all()
        )

        success = 0
        now = _now_ms()
        for event in events:
            try:
                event_ts = event.event_date or now
                self._submit_single_gee_task(
                    event, event_ts, "pre_disaster",
                    window_days=event.pre_window_days or 7,
                    allow_retry=True,  # recheck：允许越过旧 FAILED 记录重试
                )
                if event.pre_image_downloaded:
                    success += 1
                event.updated_at = now
            except Exception as e:
                logger.error(f"[{event.uuid[:8]}] recheck pre imagery 失败: {e}")

        if events:
            self.db.commit()
        return success

    # ── 6. 释放超时锁 ─────────────────────────────────────

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
