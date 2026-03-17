"""
全局事件池管理器
负责事件去重、池子维护、统计分析
"""
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.models import EventPool, Event
from utils.logger import get_logger

logger = get_logger(__name__)


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class EventPoolManager:
    """全局事件池管理器"""

    def __init__(self, db: Session):
        self.db = db

    def sync_events_to_pool(self, events_raw: List[dict]) -> Dict[str, int]:
        """
        将新抓取的事件同步到全局池
        返回: {"new": 新增数, "updated": 更新数, "total": 总数}
        """
        now = _now_ms()
        new_count = 0
        updated_count = 0

        for ev in events_raw:
            event_id = ev["event_id"]
            sub_id = ev.get("sub_id", 0)

            # 查找池中是否存在
            pool_event = (
                self.db.query(EventPool)
                .filter(
                    EventPool.event_id == event_id,
                    EventPool.sub_id == sub_id
                )
                .first()
            )

            if pool_event:
                # 更新已有事件
                pool_event.last_seen = now
                pool_event.fetch_count = (pool_event.fetch_count or 0) + 1
                
                # 更新可能变化的字段
                if ev.get("last_update") and ev["last_update"] != pool_event.last_update:
                    pool_event.last_update = ev["last_update"]
                if ev.get("severity") and ev["severity"] != pool_event.severity:
                    pool_event.severity = ev["severity"]
                if ev.get("title"):
                    pool_event.title = ev["title"]
                if ev.get("category"):
                    pool_event.category = ev["category"]
                if ev.get("category_name"):
                    pool_event.category_name = ev["category_name"]
                if ev.get("country"):
                    pool_event.country = ev["country"]
                if ev.get("continent"):
                    pool_event.continent = ev["continent"]
                if ev.get("event_date"):
                    pool_event.event_date = ev["event_date"]
                if ev.get("source_url"):
                    pool_event.source_url = ev["source_url"]
                if ev.get("longitude") is not None:
                    pool_event.longitude = ev["longitude"]
                if ev.get("latitude") is not None:
                    pool_event.latitude = ev["latitude"]
                
                updated_count += 1
            else:
                # 新增事件到池
                pool_event = EventPool(
                    event_id=event_id,
                    sub_id=sub_id,
                    title=ev["title"],
                    category=ev.get("category"),
                    category_name=ev.get("category_name"),
                    country=ev.get("country"),
                    continent=ev.get("continent"),
                    severity=ev.get("severity", "medium"),
                    longitude=ev.get("longitude"),
                    latitude=ev.get("latitude"),
                    address=ev.get("address"),
                    event_date=ev.get("event_date"),
                    last_update=ev.get("last_update"),
                    source_url=ev.get("source_url"),
                    first_seen=now,
                    last_seen=now,
                    fetch_count=1,
                    is_active=1,
                )
                self.db.add(pool_event)
                new_count += 1

        self.db.commit()
        total = self.db.query(EventPool).count()
        
        logger.info(f"事件池同步: 新增 {new_count}, 更新 {updated_count}, 总计 {total}")
        return {"new": new_count, "updated": updated_count, "total": total}

    def update_pool_coordinates(self, event_id: int, sub_id: int, 
                               longitude: float, latitude: float,
                               continent: str = None, address: str = None):
        """更新池中事件的坐标信息"""
        pool_event = (
            self.db.query(EventPool)
            .filter(
                EventPool.event_id == event_id,
                EventPool.sub_id == sub_id
            )
            .first()
        )
        
        if pool_event:
            pool_event.longitude = longitude
            pool_event.latitude = latitude
            if continent:
                pool_event.continent = continent
            if address:
                pool_event.address = address
            pool_event.last_seen = _now_ms()
            self.db.commit()

    def update_pool_details(self, event_id: int, sub_id: int, details_json: dict):
        """更新池中事件的详情"""
        pool_event = (
            self.db.query(EventPool)
            .filter(
                EventPool.event_id == event_id,
                EventPool.sub_id == sub_id
            )
            .first()
        )
        
        if pool_event:
            pool_event.details_json = json.dumps(details_json, ensure_ascii=False)
            pool_event.last_seen = _now_ms()
            self.db.commit()

    def link_event_to_pool(self, event_uuid: str, event_id: int, sub_id: int):
        """将Events表中的事件关联到池"""
        pool_event = (
            self.db.query(EventPool)
            .filter(
                EventPool.event_id == event_id,
                EventPool.sub_id == sub_id
            )
            .first()
        )
        
        if pool_event:
            pool_event.related_uuid = event_uuid
            self.db.commit()

    def deactivate_stale_events(self, days_threshold: int = 30) -> int:
        """
        标记长时间未更新的事件为不活跃
        返回: 标记数量
        """
        now = _now_ms()
        threshold_ms = days_threshold * 86400 * 1000
        cutoff = now - threshold_ms

        stale_events = (
            self.db.query(EventPool)
            .filter(
                EventPool.is_active == 1,
                EventPool.last_seen < cutoff
            )
            .all()
        )

        count = 0
        for event in stale_events:
            event.is_active = 0
            event.deactivated_at = now
            count += 1

        self.db.commit()
        logger.info(f"标记 {count} 个事件为不活跃（{days_threshold}天未更新）")
        return count

    def get_pool_stats(self) -> Dict:
        """获取池统计信息"""
        total = self.db.query(EventPool).count()
        active = self.db.query(EventPool).filter(EventPool.is_active == 1).count()
        
        # 按类别统计
        by_category = {}
        category_results = (
            self.db.query(EventPool.category, func.count(EventPool.event_id))
            .filter(EventPool.is_active == 1)
            .group_by(EventPool.category)
            .all()
        )
        for cat, cnt in category_results:
            by_category[cat or "Unknown"] = cnt

        # 按国家统计
        by_country = {}
        country_results = (
            self.db.query(EventPool.country, func.count(EventPool.event_id))
            .filter(EventPool.is_active == 1)
            .group_by(EventPool.country)
            .limit(20)
            .all()
        )
        for country, cnt in country_results:
            by_country[country or "Unknown"] = cnt

        # 按严重程度统计
        by_severity = {}
        severity_results = (
            self.db.query(EventPool.severity, func.count(EventPool.event_id))
            .filter(EventPool.is_active == 1)
            .group_by(EventPool.severity)
            .all()
        )
        for sev, cnt in severity_results:
            by_severity[sev or "unknown"] = cnt

        return {
            "total_events": total,
            "active_events": active,
            "inactive_events": total - active,
            "by_category": by_category,
            "by_country": by_country,
            "by_severity": by_severity,
        }

    def get_active_events(self, limit: int = 100, 
                         category: Optional[str] = None,
                         country: Optional[str] = None,
                         severity: Optional[str] = None) -> List[EventPool]:
        """获取活跃事件列表"""
        q = self.db.query(EventPool).filter(EventPool.is_active == 1)
        
        if category:
            q = q.filter(EventPool.category == category.upper())
        if country:
            q = q.filter(EventPool.country.ilike(f"%{country}%"))
        if severity:
            q = q.filter(EventPool.severity == severity.lower())
        
        return q.order_by(EventPool.last_seen.desc()).limit(limit).all()
