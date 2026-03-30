"""
Latest Model Open API 客户端
"""
from __future__ import annotations

import base64
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class LatestModelClient:
    """对接公网 Latest Model Open API。"""

    def __init__(self):
        self.endpoint = settings.LATEST_MODEL_ENDPOINT.rstrip("/")
        self.api_key = settings.LATEST_MODEL_API_KEY
        self.poll_interval = settings.LATEST_MODEL_POLL_INTERVAL_SECONDS
        self.max_polls = settings.LATEST_MODEL_MAX_POLLS
        self.timeout = settings.LATEST_MODEL_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def _request_json(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        headers = {}
        if payload is not None:
            headers["Content-Type"] = "application/json"

        resp = self.session.request(
            method=method,
            url=url,
            json=payload,
            headers=headers,
            timeout=timeout or self.timeout,
        )

        try:
            data = resp.json()
        except ValueError:
            data = {"error": resp.text}

        if resp.status_code >= 400:
            raise RuntimeError(
                f"Latest Model API 错误 {resp.status_code}: "
                f"{json.dumps(data, ensure_ascii=False)[:500]}"
            )
        return data

    def _encode_image(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"影像不存在: {image_path}")

        if Image is None:
            raise RuntimeError("Pillow 未安装，无法将 GeoTIFF 转为公网接口可用的图片格式")

        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((1536, 1536))
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=90, optimize=True)

        payload = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{payload}"

    def submit_tasks(self, image_path: str, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Latest Model Open API 未配置")

        payload = {
            "image_base64": self._encode_image(image_path),
            "modality": "optical",
            "tasks": tasks,
        }
        return self._request_json("POST", f"{self.endpoint}/v1/tasks", payload=payload)

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"{self.endpoint}/v1/tasks/{job_id}")

    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"{self.endpoint}/v1/tasks/{job_id}/result")

    def wait_for_result(self, job_id: str) -> Dict[str, Any]:
        last_payload: Dict[str, Any] = {}
        for _ in range(self.max_polls):
            time.sleep(self.poll_interval)
            last_payload = self.get_job_status(job_id)
            status = str(last_payload.get("status") or "").lower()
            if status == "succeeded":
                return self.get_job_result(job_id)
            if status == "failed":
                return last_payload

        raise TimeoutError(
            f"Latest Model 任务轮询超时: job_id={job_id}, "
            f"last={json.dumps(last_payload, ensure_ascii=False)[:300]}"
        )

