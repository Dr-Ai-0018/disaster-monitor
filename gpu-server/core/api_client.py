"""
公网 API 客户端
与美国公网服务器通信
"""
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class DisasterAPIClient:
    """灾害监测 API 客户端"""

    def __init__(self):
        self.base_url = settings.API_BASE_URL.rstrip("/")
        self.worker_id = settings.WORKER_ID
        self.headers = {
            "X-API-Token": settings.API_TOKEN,
            "Content-Type": "application/json",
            "User-Agent": f"DisasterWorker/{settings.WORKER_ID}/1.0",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        cfg = settings.API_CONFIG
        self.timeout = cfg.get("timeout", 300)
        self.max_retries = cfg.get("max_retries", 3)
        self.retry_delay = cfg.get("retry_delay", 10)

    # ── 任务拉取 ───────────────────────────────────────

    def pull_tasks(self, limit: int = 5) -> List[Dict]:
        """拉取待处理任务（自动锁定）"""
        url = f"{self.base_url}/api/tasks/pull"
        params = {"worker_id": self.worker_id, "limit": limit}
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            tasks = resp.json().get("tasks", [])
            logger.info(f"拉取到 {len(tasks)} 个任务")
            return tasks
        except requests.exceptions.RequestException as e:
            logger.error(f"拉取任务失败: {e}")
            return []

    # ── 心跳更新 ───────────────────────────────────────

    def update_heartbeat(self, task_uuid: str) -> bool:
        url = f"{self.base_url}/api/tasks/{task_uuid}/heartbeat"
        try:
            resp = self.session.put(url, json={"worker_id": self.worker_id}, timeout=10)
            resp.raise_for_status()
            logger.debug(f"心跳更新: {task_uuid[:8]}")
            return True
        except requests.exceptions.RequestException as e:
            logger.warning(f"心跳更新失败 {task_uuid[:8]}: {e}")
            return False

    # ── 提交结果 ───────────────────────────────────────

    def submit_result(
        self,
        task_uuid: str,
        inference_result: Dict,
        processing_time: float,
        model_info: Dict,
    ) -> bool:
        """提交推理结果（幂等，支持重试）"""
        url = f"{self.base_url}/api/tasks/{task_uuid}/result"
        payload = {
            "worker_id": self.worker_id,
            "status": "success",
            "inference_result": inference_result,
            "processing_time_seconds": processing_time,
            "model_info": model_info,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.put(url, json=payload, timeout=60)
                resp.raise_for_status()
                logger.info(f"结果提交成功: {task_uuid[:8]} (尝试 {attempt}/{self.max_retries})")
                return True
            except requests.exceptions.RequestException as e:
                logger.warning(f"结果提交失败 (尝试 {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)

        logger.error(f"结果提交最终失败: {task_uuid[:8]}")
        return False

    # ── 报告失败 ───────────────────────────────────────

    def report_failure(
        self,
        task_uuid: str,
        reason: str,
        error_details: str = "",
        can_retry: bool = True,
    ) -> bool:
        url = f"{self.base_url}/api/tasks/{task_uuid}/fail"
        payload = {
            "worker_id": self.worker_id,
            "reason": reason,
            "error_details": error_details,
            "can_retry": can_retry,
        }
        try:
            resp = self.session.put(url, json=payload, timeout=30)
            resp.raise_for_status()
            logger.info(f"失败已上报: {task_uuid[:8]}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"上报失败失败 {task_uuid[:8]}: {e}")
            return False

    # ── 下载影像 ───────────────────────────────────────

    def download_image(self, image_url: str, save_path: str) -> bool:
        """流式下载遥感影像"""
        if not image_url.startswith("http"):
            image_url = f"{self.base_url}{image_url}"

        logger.info(f"下载影像: {image_url}")
        try:
            resp = self.session.get(image_url, stream=True, timeout=self.timeout)
            resp.raise_for_status()

            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_mb = Path(save_path).stat().st_size / 1024 / 1024
            logger.info(f"影像下载完成: {Path(save_path).name} ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            logger.error(f"影像下载失败: {image_url} - {e}")
            return False

    # ── 连接测试 ───────────────────────────────────────

    def test_connection(self) -> bool:
        """测试与公网服务器的连接"""
        try:
            resp = requests.get(
                f"{self.base_url}/health", timeout=10, headers=self.headers
            )
            resp.raise_for_status()
            logger.info(f"连接测试成功: {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False
