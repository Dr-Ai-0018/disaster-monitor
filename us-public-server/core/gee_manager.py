"""
Google Earth Engine 影像管理模块
参考: Rsoe-Gee/core/gee_downloader.py
"""
import ee
import os
import time
import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Tuple

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_gee_initialized = False


def initialize_gee() -> bool:
    """应用启动时初始化 GEE（只需一次）"""
    global _gee_initialized
    if _gee_initialized:
        return True

    logger.info("初始化 Google Earth Engine...")
    try:
        sa_email = settings.GEE_SERVICE_ACCOUNT_EMAIL
        sa_path = settings.GEE_SERVICE_ACCOUNT_PATH
        project = settings.GEE_PROJECT_ID

        if sa_email and os.path.exists(sa_path):
            creds = ee.ServiceAccountCredentials(sa_email, sa_path)
            ee.Initialize(creds, project=project)
            logger.info("GEE 初始化成功（服务账号模式）")
        elif project:
            ee.Initialize(project=project)
            logger.info("GEE 初始化成功（已认证用户模式）")
        else:
            ee.Initialize()
            logger.info("GEE 初始化成功（默认模式）")

        _gee_initialized = True
        return True
    except Exception as e:
        logger.error(f"GEE 初始化失败: {e}")
        return False


class GeeManager:
    """GEE 影像下载管理器"""

    def __init__(self):
        self.cfg = settings.GEE_CONFIG
        self.images_dir = Path(settings.STORAGE_CONFIG.get("images_path", "storage/images"))
        self.images_dir.mkdir(parents=True, exist_ok=True)

    # ── 提交下载任务 ─────────────────────────────────────

    def submit_download_task(
        self,
        event_uuid: str,
        longitude: float,
        latitude: float,
        event_timestamp_ms: int,
        task_type: str = "post_disaster",
        window_days: int = None,
    ) -> Optional[str]:
        """
        提交 GEE 影像下载任务，返回结果 JSON 字符串。
        task_type: 'pre_disaster' | 'post_disaster'
        window_days: 覆盖 config 中的默认时间窗口（天数）
        """
        if not _gee_initialized:
            logger.error("GEE 未初始化，无法提交任务")
            return None

        event_dt = datetime.fromtimestamp(event_timestamp_ms / 1000, tz=timezone.utc)
        window = window_days if window_days is not None else self.cfg.get("time_window_days_before", 30)

        if task_type == "pre_disaster":
            end_dt = event_dt - timedelta(days=1)
            start_dt = end_dt - timedelta(days=window)
        else:
            start_dt = event_dt - timedelta(days=1)
            end_dt = event_dt + timedelta(days=window)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        buffer_km = self.cfg.get("buffer_km", 10)
        scale = self.cfg.get("scale", 10)
        cloud_threshold = self.cfg.get("cloud_threshold", 20)

        try:
            roi = ee.Geometry.Point([longitude, latitude]).buffer(buffer_km * 1000)

            # 尝试 Sentinel-2
            image = self._get_best_s2_image(roi, start_str, end_str, cloud_threshold)
            source = "Sentinel-2"

            if image is None:
                # 降级到 Landsat-8
                image = self._get_best_landsat_image(roi, start_str, end_str)
                source = "Landsat-8"

            if image is None:
                logger.warning(f"[{event_uuid}] 未找到合适影像 ({task_type})")
                return None

            # 获取影像日期
            image_date_ms = image.date().millis().getInfo()

            # 保存目录
            save_dir = self.images_dir / event_uuid
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{task_type}.tif"

            # 使用 getDownloadURL 直接下载
            url = image.getDownloadURL({
                "region": roi,
                "scale": scale,
                "format": "GEO_TIFF",
                "bands": ["B4", "B3", "B2"],
            })

            # 异步下载（大文件用 Export.image.toDrive，这里用直接下载）
            self._download_from_url(url, save_dir / filename)

            save_path = str(save_dir / filename)
            logger.info(f"[{event_uuid}] 影像下载完成: {save_path} ({source})")

            return json.dumps({
                "task_id": f"direct_{int(time.time())}",
                "save_path": save_path,
                "image_date_ms": image_date_ms,
                "source": source,
            })

        except Exception as e:
            logger.error(f"[{event_uuid}] GEE 任务提交失败: {e}")
            return None

    def _get_best_s2_image(self, roi, start_str, end_str, cloud_threshold):
        """获取云量最少的 Sentinel-2 影像"""
        try:
            col = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(roi)
                .filterDate(start_str, end_str)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
            )
            if col.size().getInfo() == 0:
                return None
            return col.sort("CLOUDY_PIXEL_PERCENTAGE").first().select(["B4", "B3", "B2"])
        except Exception:
            return None

    def _get_best_landsat_image(self, roi, start_str, end_str):
        """获取 Landsat-8 影像（备用）"""
        try:
            col = (
                ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                .filterBounds(roi)
                .filterDate(start_str, end_str)
                .filter(ee.Filter.lt("CLOUD_COVER", 30))
            )
            if col.size().getInfo() == 0:
                return None
            return col.sort("CLOUD_COVER").first().select(["SR_B4", "SR_B3", "SR_B2"])
        except Exception:
            return None

    def _download_from_url(self, url: str, save_path: Path):
        """流式下载文件"""
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    # ── 查询运行中任务数（配额监控） ─────────────────────

    def get_running_task_count(self) -> int:
        """返回当前 GEE 正在运行的任务数"""
        if not _gee_initialized:
            return 0
        try:
            tasks = ee.data.getTaskList()
            running = [t for t in tasks if t["state"] in ("RUNNING", "READY")]
            return len(running)
        except Exception as e:
            logger.warning(f"获取 GEE 任务数失败: {e}")
            return 0

    def is_quota_warning(self) -> bool:
        count = self.get_running_task_count()
        return count >= self.cfg.get("quota_warning_threshold", 2000)

    def is_quota_exceeded(self) -> bool:
        count = self.get_running_task_count()
        return count >= self.cfg.get("quota_pause_threshold", 2800)
