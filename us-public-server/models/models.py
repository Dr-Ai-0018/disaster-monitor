"""
SQLAlchemy ORM 模型
"""
from sqlalchemy import (
    Column, Integer, Float, Text, Boolean, create_engine, event
)
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

Base = declarative_base()


class Event(Base):
    __tablename__ = "events"

    uuid = Column(Text, primary_key=True)
    event_id = Column(Integer, nullable=False)
    sub_id = Column(Integer, default=0)
    title = Column(Text, nullable=False)
    category = Column(Text)
    category_name = Column(Text)
    country = Column(Text)
    continent = Column(Text)
    severity = Column(Text)
    longitude = Column(Float)
    latitude = Column(Float)
    address = Column(Text)
    event_date = Column(Integer)
    last_update = Column(Integer)
    details_json = Column(Text)
    source_url = Column(Text)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
    status = Column(Text, default="pending")
    pre_image_path = Column(Text)
    pre_image_date = Column(Integer)
    pre_image_downloaded = Column(Integer, default=0)
    pre_image_source = Column(Text)
    post_image_path = Column(Text)
    post_image_date = Column(Integer)
    post_image_downloaded = Column(Integer, default=0)
    post_image_source = Column(Text)
    quality_score = Column(Float)
    quality_assessment = Column(Text)
    quality_checked = Column(Integer, default=0)
    quality_pass = Column(Integer, default=0)
    quality_check_time = Column(Integer)
    # 动态影像追踪
    pre_window_days = Column(Integer, default=7)
    pre_imagery_last_check = Column(Integer)
    pre_imagery_exhausted = Column(Integer, default=0)
    post_window_days = Column(Integer, default=7)
    post_imagery_last_check = Column(Integer)
    post_imagery_open = Column(Integer, default=1)
    imagery_check_count = Column(Integer, default=0)


class GeeTask(Base):
    __tablename__ = "gee_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(Text, nullable=False)
    task_id = Column(Text)
    task_type = Column(Text, nullable=False)
    status = Column(Text, default="PENDING")
    failure_reason = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    roi_geojson = Column(Text)
    start_date = Column(Text)
    end_date = Column(Text)
    cloud_threshold = Column(Float, default=20.0)
    image_date = Column(Integer)
    image_source = Column(Text)
    download_url = Column(Text)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
    started_at = Column(Integer)
    completed_at = Column(Integer)


class TaskQueue(Base):
    __tablename__ = "task_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(Text, nullable=False, unique=True)
    task_data = Column(Text, nullable=False)
    priority = Column(Integer, default=0)
    status = Column(Text, default="pending")
    locked_by = Column(Text)
    locked_at = Column(Integer)
    locked_until = Column(Integer)
    lock_duration = Column(Integer, default=7200)
    heartbeat = Column(Integer)
    heartbeat_interval = Column(Integer, default=300)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    failure_reason = Column(Text)
    last_error_details = Column(Text)
    progress_stage = Column(Text, default="queued")
    progress_message = Column(Text)
    progress_percent = Column(Integer, default=0)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    step_details = Column(Text)
    pause_requested = Column(Integer, default=0)
    paused_at = Column(Integer)
    manual_resume_count = Column(Integer, default=0)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
    completed_at = Column(Integer)


class Product(Base):
    __tablename__ = "products"

    uuid = Column(Text, primary_key=True)
    inference_result = Column(Text, nullable=False)
    event_details = Column(Text, nullable=False)
    event_title = Column(Text)
    event_category = Column(Text)
    event_country = Column(Text)
    summary = Column(Text)
    summary_generated = Column(Integer, default=0)
    summary_generated_at = Column(Integer)
    pre_image_date = Column(Integer)
    post_image_date = Column(Integer)
    inference_quality_score = Column(Float)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(Text, nullable=False, unique=True)
    report_content = Column(Text, nullable=False)
    report_title = Column(Text)
    event_count = Column(Integer, default=0)
    category_stats = Column(Text)
    severity_stats = Column(Text)
    country_stats = Column(Text)
    generated_at = Column(Integer, nullable=False)
    generated_by = Column(Text, default="gemini-flash")
    generation_time_seconds = Column(Float)
    published = Column(Integer, default=0)
    published_at = Column(Integer)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    email = Column(Text)
    full_name = Column(Text)
    role = Column(Text, default="admin")
    permissions = Column(Text)
    is_active = Column(Integer, default=1)
    created_at = Column(Integer, nullable=False)
    last_login = Column(Integer)
    login_count = Column(Integer, default=0)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    token = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    scopes = Column(Text)
    is_active = Column(Integer, default=1)
    last_used = Column(Integer)
    usage_count = Column(Integer, default=0)
    created_at = Column(Integer, nullable=False)
    expires_at = Column(Integer)
    created_by = Column(Integer)


class EventPool(Base):
    """全局事件池 - 所有爬取到的事件去重后的总池"""
    __tablename__ = "event_pool"

    event_id = Column(Integer, primary_key=True)
    sub_id = Column(Integer, primary_key=True, default=0)
    title = Column(Text, nullable=False)
    category = Column(Text)
    category_name = Column(Text)
    country = Column(Text)
    continent = Column(Text)
    severity = Column(Text)
    longitude = Column(Float)
    latitude = Column(Float)
    address = Column(Text)
    event_date = Column(Integer)
    last_update = Column(Integer)
    details_json = Column(Text)
    source_url = Column(Text)
    first_seen = Column(Integer, nullable=False)
    last_seen = Column(Integer, nullable=False)
    fetch_count = Column(Integer, default=1)
    is_active = Column(Integer, default=1)
    deactivated_at = Column(Integer)
    related_uuid = Column(Text)


# ──────────────────────────────────────────
# 数据库会话工厂
# ──────────────────────────────────────────

_engine = None
_SessionLocal = None


def get_engine(db_url: str = None):
    global _engine
    if _engine is None:
        if db_url is None:
            from config.settings import settings
            db_url = "sqlite:///" + settings.DATABASE_PATH
        Path(db_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            db_url,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,          # 写锁等待 30s，而不是立即报 "database is locked"
            },
            echo=False,
        )
        # 启用 WAL 模式提升并发性能
        @event.listens_for(_engine, "connect")
        def set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")  # WAL 下 NORMAL 足够安全且更快
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return _engine


def get_session_factory(db_url: str = None):
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(db_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db():
    """FastAPI 依赖注入：数据库会话"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
