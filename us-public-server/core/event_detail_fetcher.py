"""
事件详情补抓管理器
"""
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from core.event_pool_manager import EventPoolManager
from core.rsoe_spider import RsoeSpider
from models.models import Event
from utils.logger import get_logger

logger = get_logger(__name__)

DETAIL_STATUS_PENDING = "pending"
DETAIL_STATUS_SUCCESS = "success"
DETAIL_STATUS_NOT_FOUND = "not_found"
DETAIL_STATUS_FAILED = "failed"


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _source_url_to_ids(source_url: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not source_url:
        return None, None
    match = re.search(r"/details/(\d+)(?:/(\d+))?", source_url)
    if not match:
        return None, None
    event_id = int(match.group(1))
    sub_id = int(match.group(2) or 0)
    return event_id, sub_id


class EventDetailFetcher:
    """为新入库且详情为空的事件补抓详细信息。"""

    def __init__(self, db: Session):
        self.db = db
        self.spider = RsoeSpider()
        self.pool_manager = EventPoolManager(db)

    def _build_candidates(self, limit: int) -> list[Event]:
        query = (
            self.db.query(Event)
            .filter(
                Event.source_url.isnot(None),
                (Event.details_json.is_(None)) | (Event.details_json == ""),
                ((Event.detail_fetch_status.is_(None)) | (Event.detail_fetch_status != DETAIL_STATUS_NOT_FOUND)),
            )
            .order_by(Event.created_at.asc(), Event.updated_at.asc())
            .limit(limit)
        )
        return query.all()

    def _fetch_one(self, event: Event) -> Dict[str, Any]:
        delay_min = settings.DETAIL_FETCH_DELAY_MIN_SECONDS
        delay_max = settings.DETAIL_FETCH_DELAY_MAX_SECONDS
        if delay_max > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        event_id, sub_id = _source_url_to_ids(event.source_url)
        if event_id is None:
            return {
                "uuid": event.uuid,
                "success": False,
                "status": DETAIL_STATUS_FAILED,
                "http_status": None,
                "error": f"无法从 source_url 解析事件ID: {event.source_url}",
            }

        result = self.spider.fetch_event_detail_result(
            event_id,
            sub_id or 0,
            timeout=settings.DETAIL_FETCH_TIMEOUT_SECONDS,
        )
        result["uuid"] = event.uuid
        return result

    def fetch_missing_details(self, limit: Optional[int] = None) -> Dict[str, int]:
        if not settings.DETAIL_FETCH_ENABLED:
            return {"processed": 0, "success": 0, "not_found": 0, "failed": 0, "skipped": 0}

        batch_size = limit or settings.DETAIL_FETCH_BATCH_SIZE
        candidates = self._build_candidates(batch_size)
        if not candidates:
            return {"processed": 0, "success": 0, "not_found": 0, "failed": 0, "skipped": 0}

        stats = {"processed": 0, "success": 0, "not_found": 0, "failed": 0, "skipped": 0}
        event_map = {event.uuid: event for event in candidates}

        with ThreadPoolExecutor(max_workers=settings.DETAIL_FETCH_CONCURRENCY) as executor:
            future_map = {executor.submit(self._fetch_one, event): event.uuid for event in candidates}

            for future in as_completed(future_map):
                uuid = future_map[future]
                event = event_map.get(uuid)
                if not event:
                    stats["skipped"] += 1
                    continue

                now = _now_ms()
                event.detail_fetch_attempts = (event.detail_fetch_attempts or 0) + 1
                event.detail_fetch_last_attempt = now
                event.updated_at = now

                try:
                    result = future.result()
                except Exception as e:
                    event.detail_fetch_status = DETAIL_STATUS_FAILED
                    event.detail_fetch_error = str(e)
                    stats["failed"] += 1
                    logger.error(f"[{uuid[:8]}] 详情补抓异常: {e}")
                    continue

                stats["processed"] += 1
                status = result.get("status")
                http_status = result.get("http_status")
                event.detail_fetch_http_status = http_status

                if result.get("success"):
                    detail = result.get("detail") or {}
                    event.detail_fetch_status = DETAIL_STATUS_SUCCESS
                    event.detail_fetch_error = None
                    event.detail_fetch_completed_at = now
                    event.details_json = json.dumps(detail.get("details_json", {}), ensure_ascii=False)
                    event.address = detail.get("address") or event.address
                    event.continent = detail.get("continent") or event.continent
                    event.country = detail.get("country") or event.country
                    event.category = detail.get("category") or event.category
                    event.category_name = detail.get("category_name") or event.category_name
                    event.severity = detail.get("severity") or event.severity
                    event.event_date = detail.get("event_date") or event.event_date
                    if detail.get("last_update"):
                        event.last_update = detail["last_update"]
                    if detail.get("longitude") is not None:
                        event.longitude = detail.get("longitude")
                    if detail.get("latitude") is not None:
                        event.latitude = detail.get("latitude")

                    if detail.get("details_json"):
                        self.pool_manager.update_pool_details(event.event_id, event.sub_id, detail["details_json"])
                    if event.longitude is not None and event.latitude is not None:
                        self.pool_manager.update_pool_coordinates(
                            event.event_id,
                            event.sub_id,
                            event.longitude,
                            event.latitude,
                            event.continent,
                            event.address,
                        )

                    stats["success"] += 1
                    logger.info(f"[{uuid[:8]}] 事件详情补抓成功")
                    continue

                event.detail_fetch_status = status or DETAIL_STATUS_FAILED
                event.detail_fetch_error = result.get("error")
                if status == DETAIL_STATUS_NOT_FOUND:
                    stats["not_found"] += 1
                    logger.warning(f"[{uuid[:8]}] 事件详情返回 404，后续将跳过")
                else:
                    stats["failed"] += 1
                    logger.warning(
                        f"[{uuid[:8]}] 事件详情补抓失败: status={event.detail_fetch_status}, "
                        f"http_status={http_status}, error={event.detail_fetch_error}"
                    )

        self.db.commit()
        return stats
