from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv


class Settings:
    def __init__(self):
        self.PROJECT_ROOT = Path(__file__).resolve().parent.parent
        self.LEGACY_ROOT = Path(
            os.getenv(
                "LEGACY_SERVER_ROOT",
                str((self.PROJECT_ROOT.parent / "us-public-server").resolve()),
            )
        )
        self.LEGACY_ENV_PATH = Path(
            os.getenv("LEGACY_ENV_PATH", str((self.LEGACY_ROOT / ".env").resolve()))
        )
        if self.LEGACY_ENV_PATH.exists():
            load_dotenv(self.LEGACY_ENV_PATH, override=False)
        load_dotenv(override=False)
        self._load_env()
        self._load_json()

    def _load_env(self):
        self.APP_NAME = os.getenv("APP_NAME", "DisasterWorkflowServer")
        self.APP_ENV = os.getenv("APP_ENV", "development")
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )
        self.SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
        self.SERVER_PORT = int(os.getenv("SERVER_PORT", "2335"))
        self.SERVER_WORKERS = int(os.getenv("SERVER_WORKERS", "1"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.WORKFLOW_PROJECTION_REFRESH_INTERVAL_MS = int(
            os.getenv("WORKFLOW_PROJECTION_REFRESH_INTERVAL_MS", "30000")
        )
        self.LOG_FILE = os.getenv(
            "LOG_FILE",
            str((self.PROJECT_ROOT / "logs" / "workflow.log").resolve()),
        )
        self.ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
        self.LEGACY_PYTHON = os.getenv("LEGACY_PYTHON", self._detect_legacy_python())
        self.SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")

        self.SESSION_EDIS_WEB = os.getenv("SESSION_EDIS_WEB", "")
        self.ARR_AFFINITY = os.getenv("ARR_AFFINITY", "")
        self.ARR_AFFINITY_SAME_SITE = os.getenv("ARR_AFFINITY_SAME_SITE", "")
        self.GA = os.getenv("_GA", "")
        self.GADS = os.getenv("__GADS", "")
        self.GPI = os.getenv("__GPI", "")
        self.EOI = os.getenv("__EOI", "")
        self.GA_KHD7YP5VHW = os.getenv("_GA_KHD7YP5VHW", "")

        self.DETAIL_FETCH_ENABLED = os.getenv("DETAIL_FETCH_ENABLED", "true").lower() == "true"
        self.DETAIL_FETCH_RUN_ON_STARTUP = os.getenv("DETAIL_FETCH_RUN_ON_STARTUP", "true").lower() == "true"
        self.DETAIL_FETCH_INTERVAL_MINUTES = int(os.getenv("DETAIL_FETCH_INTERVAL_MINUTES", "10"))
        self.DETAIL_FETCH_BATCH_SIZE = int(os.getenv("DETAIL_FETCH_BATCH_SIZE", "20"))
        self.DETAIL_FETCH_CONCURRENCY = max(1, int(os.getenv("DETAIL_FETCH_CONCURRENCY", "1")))
        self.DETAIL_FETCH_DELAY_MIN_SECONDS = float(os.getenv("DETAIL_FETCH_DELAY_MIN_SECONDS", "1"))
        self.DETAIL_FETCH_DELAY_MAX_SECONDS = float(os.getenv("DETAIL_FETCH_DELAY_MAX_SECONDS", "3"))
        self.DETAIL_FETCH_TIMEOUT_SECONDS = int(
            os.getenv("DETAIL_FETCH_TIMEOUT_SECONDS", str(self.REQUEST_TIMEOUT))
        )

        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url:
            if database_url.startswith("sqlite:///"):
                raw_path = database_url[len("sqlite:///"):]
                db_path = Path(raw_path)
                if not db_path.is_absolute():
                    # Legacy env files often use a repo-relative sqlite path like
                    # `sqlite:///database/disaster.db`; resolve it against the
                    # legacy server root instead of the workflow server cwd.
                    db_path = (self.LEGACY_ROOT / db_path).resolve()
                self.DATABASE_PATH = str(db_path)
                self.DATABASE_URL = "sqlite:///" + self.DATABASE_PATH
            else:
                self.DATABASE_URL = database_url
                self.DATABASE_PATH = database_url.replace("sqlite:///", "")
        else:
            self.DATABASE_PATH = str((self.LEGACY_ROOT / "database" / "disaster.db").resolve())
            self.DATABASE_URL = "sqlite:///" + self.DATABASE_PATH

        cors_str = os.getenv("CORS_ORIGINS", "http://localhost:2335,http://localhost:3000")
        self.CORS_ORIGINS: List[str] = [item.strip() for item in cors_str.split(",") if item.strip()]

    def _load_json(self):
        config_path = Path(
            os.getenv(
                "LEGACY_CONFIG_PATH",
                str((self.LEGACY_ROOT / "config.json").resolve()),
            )
        )
        self.LEGACY_CONFIG_PATH = config_path
        self._config: dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)

        self.SCHEDULER_CONFIG = self._config.get("scheduler", {})
        self.RSOE_CONFIG = self._config.get("rsoe", {})
        self.GEE_CONFIG = self._config.get("gee", {})
        self.TASK_QUEUE_CONFIG = self._config.get("task_queue", {})
        self.STORAGE_CONFIG = self._config.get("storage", {})
        self.QUALITY_CONFIG = self._config.get("quality_assessment", {})

        if self.DETAIL_FETCH_DELAY_MAX_SECONDS < self.DETAIL_FETCH_DELAY_MIN_SECONDS:
            self.DETAIL_FETCH_DELAY_MAX_SECONDS = self.DETAIL_FETCH_DELAY_MIN_SECONDS

    def _detect_legacy_python(self) -> str:
        candidates = [
            self.LEGACY_ROOT / ".venv" / "Scripts" / "python.exe",
            self.LEGACY_ROOT / ".venv" / "bin" / "python",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate.resolve())
        return sys.executable

    def get_rsoe_cookies(self) -> dict[str, str]:
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

    def get_rsoe_headers(self) -> dict[str, str]:
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

    def get_rsoe_api_headers(self, event_id: int, sub_id: int) -> dict[str, str]:
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

    def get(self, key: str, default: Any = None) -> Any:
        value: Any = self._config
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
        return value if value is not None else default


settings = Settings()
