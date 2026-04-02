from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

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


class RsoeSpider:
    BASE_URL = "https://rsoe-edis.org"
    EVENT_LIST_API = "https://rsoe-edis.org/gateway/webapi/events"
    EVENT_DETAIL_API = "https://rsoe-edis.org/gateway/webapi/events/get"

    def __init__(self):
        self.html_dir = Path(settings.STORAGE_CONFIG.get("html_path", "storage/html"))
        self.json_dir = Path(settings.STORAGE_CONFIG.get("json_path", "storage/json"))
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    def fetch_event_list(self) -> List[Dict]:
        logger.info("开始抓取 RSOE 事件列表...")
        try:
            resp = requests.get(
                self.EVENT_LIST_API,
                headers=settings.get_rsoe_headers(),
                cookies=settings.get_rsoe_cookies(),
                timeout=settings.RSOE_CONFIG.get("request_timeout", settings.REQUEST_TIMEOUT),
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errorCode") != 0:
                logger.error(f"RSOE API 返回错误: {data.get('errorMessage')}")
                return []
            features = data.get("features", [])
            events: List[Dict] = []
            for feature in features:
                event = self._parse_feature(feature)
                if event:
                    events.append(event)
            logger.info(f"解析到 {len(events)} 个事件")
            return events
        except Exception as e:
            logger.error(f"抓取事件列表失败: {e}")
            return []

    def _parse_feature(self, feature: Dict) -> Optional[Dict]:
        try:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            event_id = props.get("id")
            if not event_id:
                return None
            parts = str(event_id).split("-")
            main_id = int(parts[0])
            sub_id = int(parts[1]) if len(parts) > 1 else 0
            return {
                "event_id": main_id,
                "sub_id": sub_id,
                "title": props.get("title", "Unknown Event"),
                "category": props.get("category", "Unknown"),
                "category_name": props.get("categoryName")
                or CATEGORY_MAP.get(props.get("category", "Unknown"), props.get("category", "Unknown")),
                "severity": props.get("severity", "medium"),
                "country": props.get("country") or props.get("countryName", ""),
                "continent": props.get("continent") or props.get("continentName", ""),
                "longitude": coords[0] if len(coords) >= 2 else None,
                "latitude": coords[1] if len(coords) >= 2 else None,
                "event_date": props.get("eventDate"),
                "last_update": props.get("lastUpdate"),
                "source_url": f"{self.BASE_URL}/eventList/details/{main_id}/{sub_id}",
            }
        except Exception as e:
            logger.debug(f"解析 feature 失败: {e}")
            return None

    def fetch_event_detail_result(
        self,
        event_id: int,
        sub_id: int = 0,
        timeout: Optional[int] = None,
    ) -> Dict:
        url = f"{self.EVENT_DETAIL_API}/{event_id}/{sub_id}"
        try:
            resp = requests.get(
                url,
                headers=settings.get_rsoe_api_headers(event_id, sub_id),
                cookies=settings.get_rsoe_cookies(),
                timeout=timeout or settings.RSOE_CONFIG.get("request_timeout", settings.REQUEST_TIMEOUT),
            )

            if resp.status_code == 404:
                return {
                    "success": False,
                    "status": "not_found",
                    "http_status": 404,
                    "error": f"事件详情不存在: {event_id}/{sub_id}",
                }

            resp.raise_for_status()
            data = resp.json()
            if data.get("errorCode") not in (None, 0):
                error_message = data.get("errorMessage") or "RSOE 详情接口返回错误"
                return {
                    "success": False,
                    "status": "failed",
                    "http_status": resp.status_code,
                    "error": error_message,
                }

            features = data.get("features") or []
            feature = features[0] if features else {}
            props = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            lon, lat = self._extract_coords(feature if feature else data)
            continent = props.get("continent") or props.get("continentName") or data.get("affectedRegion", "")
            address = props.get("address") or props.get("location") or data.get("location") or ""
            last_update = props.get("lastUpdate") or data.get("lastUpdate")

            return {
                "success": True,
                "status": "success",
                "http_status": resp.status_code,
                "detail": {
                    "longitude": lon,
                    "latitude": lat,
                    "continent": continent,
                    "address": address,
                    "last_update": last_update,
                    "details_json": data,
                    "geometry_type": geometry.get("type"),
                    "title": props.get("title"),
                    "category": props.get("category"),
                    "category_name": props.get("categoryName"),
                    "country": props.get("country") or props.get("countryName"),
                    "severity": props.get("severity"),
                    "event_date": props.get("eventDate"),
                },
            }
        except Exception as e:
            logger.error(f"获取事件详情失败 {event_id}/{sub_id}: {e}")
            status_code = None
            if isinstance(e, requests.HTTPError) and getattr(e, "response", None) is not None:
                status_code = e.response.status_code
            return {
                "success": False,
                "status": "failed",
                "http_status": status_code,
                "error": str(e),
            }

    def _extract_coords(self, data: Dict) -> Tuple[Optional[float], Optional[float]]:
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

        lon = data.get("longitude") or data.get("lon") or data.get("lng")
        lat = data.get("latitude") or data.get("lat")
        if lon and lat:
            return float(lon), float(lat)
        return None, None

    def _flatten_coords(self, obj) -> List:
        if not obj:
            return []
        if isinstance(obj[0], (int, float)):
            return [obj]
        result = []
        for item in obj:
            result.extend(self._flatten_coords(item))
        return result


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
