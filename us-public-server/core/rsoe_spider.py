"""
RSOE 数据抓取与解析模块
参考: Rsoe-Gee/core/rsoe_spider.py + Rsoe-Gee/core/rsoe_detail.py
"""
import uuid
import time
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

CATEGORY_MAP = {
    "EQ": "Earthquake",
    "FL": "Flood",
    "FI": "Fire",
    "TC": "Tropical Cyclone",
    "VO": "Volcano",
    "DR": "Drought",
    "LS": "Landslide",
    "WA": "Tsunami",
    "SS": "Storm Surge",
    "CI": "Collapse / Infrastructure",
    "EP": "Epidemic",
    "AC": "Industrial Accident",
    "TO": "Tornado",
    "EC": "Extreme Cold",
    "EH": "Extreme Heat",
    "WI": "Winter Storm",
    "AV": "Avalanche",
}

SEVERITY_MAP = {
    "extreme": "extreme",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


class RsoeSpider:
    """RSOE 爬虫 —— 抓取事件列表并存储"""

    BASE_URL = "https://rsoe-edis.org"
    EVENT_LIST_API = "https://rsoe-edis.org/gateway/webapi/events"
    EVENT_DETAIL_API = "https://rsoe-edis.org/gateway/webapi/events/get"

    def __init__(self):
        self.html_dir = Path(settings.STORAGE_CONFIG.get("html_path", "storage/html"))
        self.json_dir = Path(settings.STORAGE_CONFIG.get("json_path", "storage/json"))
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    # ── 抓取事件列表（直接调用 API）──────────────────────────────

    def fetch_event_list(self) -> List[Dict]:
        """直接调用 RSOE API 获取事件列表，返回事件列表"""
        logger.info("开始抓取 RSOE 事件列表...")
        try:
            resp = requests.get(
                self.EVENT_LIST_API,
                headers=settings.get_rsoe_headers(),
                cookies=settings.get_rsoe_cookies(),
                timeout=settings.RSOE_CONFIG.get("request_timeout", 30),
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("errorCode") != 0:
                logger.error(f"RSOE API 返回错误: {data.get('errorMessage')}")
                return []
            
            features = data.get("features", [])
            events = []
            
            for feature in features:
                try:
                    event = self._parse_feature(feature)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.debug(f"解析事件失败: {e}")
            
            logger.info(f"解析到 {len(events)} 个事件")
            return events
        except Exception as e:
            logger.error(f"抓取事件列表失败: {e}")
            return []

    def _parse_feature(self, feature: Dict) -> Optional[Dict]:
        """解析单个事件 feature"""
        try:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            
            # 提取事件 ID
            event_id = props.get("id")
            if not event_id:
                return None
            
            # 解析 ID 格式：可能是 "123456" 或 "123456-0"
            parts = str(event_id).split("-")
            main_id = int(parts[0])
            sub_id = int(parts[1]) if len(parts) > 1 else 0
            
            return {
                "event_id": main_id,
                "sub_id": sub_id,
                "title": props.get("title", "Unknown Event"),
                "category": props.get("category", "Unknown"),
                "severity": props.get("severity", "medium"),
                "country": props.get("country", ""),
                "continent": props.get("continent", ""),
                "longitude": coords[0] if len(coords) >= 2 else None,
                "latitude": coords[1] if len(coords) >= 2 else None,
                "event_date": props.get("eventDate"),
                "last_update": props.get("lastUpdate"),
                "source_url": f"{self.BASE_URL}/eventList/details/{main_id}/{sub_id}",
            }
        except Exception as e:
            logger.debug(f"解析 feature 失败: {e}")
            return None

    def parse_event_list(self, html_path: Path) -> List[Dict]:
        """已废弃：保留兼容性"""
        logger.warning("parse_event_list 已废弃，请直接使用 fetch_event_list")
        return []

    def _parse_row(self, row, cols) -> Optional[Dict]:
        """解析单行事件"""
        # 提取 event_id / sub_id
        link = row.find("a", href=True)
        event_id, sub_id = None, 0
        if link:
            href = link["href"]
            parts = href.strip("/").split("/")
            for i, p in enumerate(parts):
                if p == "details" and i + 1 < len(parts):
                    try:
                        event_id = int(parts[i + 1])
                        if i + 2 < len(parts):
                            sub_id = int(parts[i + 2])
                    except ValueError:
                        pass

        if event_id is None:
            return None

        title = cols[0].get_text(strip=True) if len(cols) > 0 else ""
        category_raw = cols[1].get_text(strip=True) if len(cols) > 1 else ""
        category = category_raw.upper()[:2] if category_raw else "UN"
        severity_raw = (row.get("class") or [""])[0].lower()
        severity = SEVERITY_MAP.get(severity_raw, "medium")
        country = cols[2].get_text(strip=True) if len(cols) > 2 else ""
        date_str = cols[3].get_text(strip=True) if len(cols) > 3 else ""
        event_date = self._parse_date(date_str)

        return {
            "event_id": event_id,
            "sub_id": sub_id,
            "title": title,
            "category": category,
            "category_name": CATEGORY_MAP.get(category, category_raw),
            "country": country,
            "severity": severity,
            "event_date": event_date,
            "last_update": event_date,
            "source_url": f"{self.BASE_URL}/eventList/details/{event_id}/{sub_id}",
        }

    def _parse_date(self, date_str: str) -> Optional[int]:
        """解析日期字符串为毫秒时间戳"""
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            except ValueError:
                continue
        return None

    # ── 获取事件详情（坐标 + JSON） ──────────────────────

    def fetch_event_detail(self, event_id: int, sub_id: int = 0) -> Optional[Dict]:
        """从 RSOE API 获取事件详情，含坐标"""
        url = f"{self.EVENT_API_URL}/{event_id}/{sub_id}"
        try:
            resp = requests.get(
                url,
                headers=settings.get_rsoe_api_headers(event_id, sub_id),
                cookies=settings.get_rsoe_cookies(),
                timeout=settings.RSOE_CONFIG.get("request_timeout", 30),
            )
            resp.raise_for_status()
            data = resp.json()

            lon, lat = self._extract_coords(data)
            continent = data.get("continent") or data.get("affectedRegion", "")
            address = data.get("address") or data.get("location") or ""
            last_update_str = data.get("lastUpdated") or data.get("updateTime")
            last_update = self._parse_date(last_update_str) if last_update_str else None

            return {
                "longitude": lon,
                "latitude": lat,
                "continent": continent,
                "address": address,
                "last_update": last_update,
                "details_json": data,
            }
        except Exception as e:
            logger.error(f"获取事件详情失败 {event_id}/{sub_id}: {e}")
            return None

    def _extract_coords(self, data: Dict) -> Tuple[Optional[float], Optional[float]]:
        """从 API 响应中提取坐标"""
        geometry = data.get("geometry") or {}
        geo_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])

        try:
            if geo_type == "Point" and len(coords) >= 2:
                return float(coords[0]), float(coords[1])
            if geo_type in ("Polygon", "MultiPolygon", "LineString"):
                flat = self._flatten_coords(coords)
                if flat:
                    lons = [c[0] for c in flat]
                    lats = [c[1] for c in flat]
                    return sum(lons) / len(lons), sum(lats) / len(lats)
        except Exception:
            pass

        # 直接字段
        lon = data.get("longitude") or data.get("lon") or data.get("lng")
        lat = data.get("latitude") or data.get("lat")
        if lon and lat:
            return float(lon), float(lat)
        return None, None

    def _flatten_coords(self, obj) -> List:
        """展平嵌套坐标列表"""
        if not obj:
            return []
        if isinstance(obj[0], (int, float)):
            return [obj]
        result = []
        for item in obj:
            result.extend(self._flatten_coords(item))
        return result
