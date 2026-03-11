"""
GPU 服务器配置模块
"""
import os
import json
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """GPU Worker 配置"""

    def __init__(self):
        self._load_env()
        self._load_json()

    def _load_env(self):
        self.WORKER_ID = os.getenv("WORKER_ID", "gpu-server-1")
        self.WORKER_NAME = os.getenv("WORKER_NAME", "GPU Server 1")

        # 关键：API 地址作为全局变量，便于切换开发/生产
        self.API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        self.API_TOKEN = os.getenv("API_TOKEN", "")

        self.MODEL_NAME = os.getenv("MODEL_NAME", "disaster-recognition-v1")
        self.MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")
        self.MODEL_PATH = os.getenv("MODEL_PATH", "models/disaster_model")

        # GPU
        self.CUDA_VISIBLE_DEVICES = os.getenv("CUDA_VISIBLE_DEVICES", "0")
        os.environ["CUDA_VISIBLE_DEVICES"] = self.CUDA_VISIBLE_DEVICES

        # 轮询
        self.POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))
        self.HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "300"))
        self.MAX_TASKS_PER_PULL = int(os.getenv("MAX_TASKS_PER_PULL", "5"))

        # 推理
        self.MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", "1024"))

        # 日志
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "logs/gpu_worker.log")

        # 临时目录
        self.TEMP_DIR = os.getenv("TEMP_DIR", "temp")

    def _load_json(self):
        config_path = Path("config.json")
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

        self.WORKER_CONFIG = self._config.get("worker", {})
        self.API_CONFIG = self._config.get("api", {})
        self.MODEL_CONFIG = self._config.get("model", {})
        self.INFERENCE_CONFIG = self._config.get("inference", {})
        self.TASKS_CONFIG = self._config.get("tasks", {})
        self.STORAGE_CONFIG = self._config.get("storage", {})
        self.POLLING_CONFIG = self._config.get("polling", {})

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        val = self._config
        for k in parts:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def validate(self) -> bool:
        if not self.API_TOKEN:
            raise ValueError("API_TOKEN 未配置，请设置环境变量 API_TOKEN")
        if not self.API_BASE_URL:
            raise ValueError("API_BASE_URL 未配置")
        return True


settings = Settings()
