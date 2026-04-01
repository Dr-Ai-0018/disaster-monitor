"""
配置管理模块
"""
import os
import json
from pathlib import Path
from typing import Any, List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """全局配置类"""

    def __init__(self):
        self._load_env()
        self._load_json()

    def _load_env(self):
        # 应用
        self.APP_NAME = os.getenv("APP_NAME", "DisasterMonitoringSystem")
        self.APP_ENV = os.getenv("APP_ENV", "development")
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

        # 数据库
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/disaster.db")
        self.DATABASE_PATH = self.DATABASE_URL.replace("sqlite:///", "")

        # RSOE Cookie
        self.SESSION_EDIS_WEB = os.getenv("SESSION_EDIS_WEB", "")
        self.ARR_AFFINITY = os.getenv("ARR_AFFINITY", "")
        self.ARR_AFFINITY_SAME_SITE = os.getenv("ARR_AFFINITY_SAME_SITE", "")
        self.GA = os.getenv("_GA", "")
        self.GADS = os.getenv("__GADS", "")
        self.GPI = os.getenv("__GPI", "")
        self.EOI = os.getenv("__EOI", "")
        self.GA_KHD7YP5VHW = os.getenv("_GA_KHD7YP5VHW", "")

        # GEE
        self.GEE_PROJECT_ID = os.getenv("GEE_PROJECT_ID", "")
        self.GEE_SERVICE_ACCOUNT_EMAIL = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL", "")
        self.GEE_SERVICE_ACCOUNT_PATH = os.getenv(
            "GEE_SERVICE_ACCOUNT_PATH", "config/service_account.json"
        )

        # OpenAI
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

        # Gemini
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.GEMINI_BASE_URL = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        )
        self.GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.0-flash")
        self.GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro-preview-03-25")

        # Latest Model Open API
        self.LATEST_MODEL_ENDPOINT = os.getenv(
            "LATEST_MODEL_ENDPOINT", "https://frp-geo.killerbest.com"
        )
        self.LATEST_MODEL_API_KEY = os.getenv("LATEST_MODEL_API_KEY", "")
        self.LATEST_MODEL_TIMEOUT_SECONDS = int(
            os.getenv("LATEST_MODEL_TIMEOUT_SECONDS", "60")
        )
        self.LATEST_MODEL_POLL_INTERVAL_SECONDS = float(
            os.getenv("LATEST_MODEL_POLL_INTERVAL_SECONDS", "2")
        )
        self.LATEST_MODEL_MAX_POLLS = int(os.getenv("LATEST_MODEL_MAX_POLLS", "180"))

        # JWT
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )

        # 初始化默认管理员
        self.SEED_ADMIN_ENABLED = os.getenv("SEED_ADMIN_ENABLED", "true").lower() == "true"
        self.SEED_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "user-707")
        self.SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "srgYJKmvr953yj")
        self.SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "0example@killerbest.com")
        self.SEED_ADMIN_FULL_NAME = os.getenv("SEED_ADMIN_FULL_NAME", "System Administrator")

        # 服务器
        self.SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
        self.SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
        self.SERVER_WORKERS = int(os.getenv("SERVER_WORKERS", "4"))
        self.REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
        self.SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")

        # 事件详情补抓
        self.DETAIL_FETCH_ENABLED = os.getenv("DETAIL_FETCH_ENABLED", "true").lower() == "true"
        self.DETAIL_FETCH_RUN_ON_STARTUP = os.getenv("DETAIL_FETCH_RUN_ON_STARTUP", "true").lower() == "true"
        self.DETAIL_FETCH_INTERVAL_MINUTES = int(os.getenv("DETAIL_FETCH_INTERVAL_MINUTES", "10"))
        self.DETAIL_FETCH_BATCH_SIZE = int(os.getenv("DETAIL_FETCH_BATCH_SIZE", "20"))
        self.DETAIL_FETCH_CONCURRENCY = max(1, int(os.getenv("DETAIL_FETCH_CONCURRENCY", "1")))
        self.DETAIL_FETCH_DELAY_MIN_SECONDS = float(os.getenv("DETAIL_FETCH_DELAY_MIN_SECONDS", "1"))
        self.DETAIL_FETCH_DELAY_MAX_SECONDS = float(os.getenv("DETAIL_FETCH_DELAY_MAX_SECONDS", "3"))
        self.DETAIL_FETCH_TIMEOUT_SECONDS = int(os.getenv("DETAIL_FETCH_TIMEOUT_SECONDS", str(self.REQUEST_TIMEOUT)))

        cors_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
        self.CORS_ORIGINS: List[str] = [o.strip() for o in cors_str.split(",") if o.strip()]

        # 日志
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "logs/disaster.log")

    def _load_json(self):
        config_path = Path("config.json")
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

        self.RSOE_CONFIG = self._config.get("rsoe", {})
        self.GEE_CONFIG = self._config.get("gee", {})
        self.SCHEDULER_CONFIG = self._config.get("scheduler", {})
        self.TASK_QUEUE_CONFIG = self._config.get("task_queue", {})
        self.STORAGE_CONFIG = self._config.get("storage", {})
        self.QUALITY_CONFIG = self._config.get("quality_assessment", {})
        self.REPORT_CONFIG = self._config.get("report_generation", {})

        if self.DETAIL_FETCH_DELAY_MAX_SECONDS < self.DETAIL_FETCH_DELAY_MIN_SECONDS:
            self.DETAIL_FETCH_DELAY_MAX_SECONDS = self.DETAIL_FETCH_DELAY_MIN_SECONDS

    def get(self, key: str, default: Any = None) -> Any:
        """点号路径获取 JSON 配置"""
        parts = key.split(".")
        val = self._config
        for k in parts:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def get_rsoe_cookies(self) -> dict:
        return {
            "session_edis_web": self.SESSION_EDIS_WEB,
            "ARRAffinity": self.ARR_AFFINITY,
            "ARRAffinitySameSite": self.ARR_AFFINITY_SAME_SITE,
            "_ga": self.GA,
            "__gads": self.GADS,
            "__gpi": self.GPI,
            "__eoi": self.EOI,
            "_ga_KHD7YP5VHW": self.GA_KHD7YP5VHW,
        }

    def get_rsoe_headers(self) -> dict:
        base = self.RSOE_CONFIG.get("base_url", "https://rsoe-edis.org")
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": base + "/services",
        }

    def get_rsoe_api_headers(self, event_id, sub_id) -> dict:
        base = self.RSOE_CONFIG.get("base_url", "https://rsoe-edis.org")
        return {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{base}/eventList/details/{event_id}/{sub_id}",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }

    def validate(self) -> bool:
        missing = []
        for key in ["SECRET_KEY", "JWT_SECRET_KEY"]:
            val = getattr(self, key, None)
            if not val or val.startswith("dev-"):
                missing.append(key)
        if missing and self.APP_ENV == "production":
            raise ValueError(f"生产环境缺少必需配置: {', '.join(missing)}")
        return True


settings = Settings()
