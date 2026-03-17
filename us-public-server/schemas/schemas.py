"""
Pydantic 请求/响应模型
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# Auth
# ──────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: int
    username: str
    role: str


class LoginResponse(TokenResponse):
    user: UserInfo


# ──────────────────────────────────────────
# Events
# ──────────────────────────────────────────

class EventSummary(BaseModel):
    uuid: str
    event_id: int
    sub_id: int
    title: str
    category: Optional[str]
    category_name: Optional[str]
    country: Optional[str]
    continent: Optional[str]
    severity: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    event_date: Optional[int]
    last_update: Optional[int]
    status: str
    pre_image_downloaded: bool
    post_image_downloaded: bool
    quality_pass: bool
    created_at: int
    updated_at: int
    # 动态影像追踪
    pre_window_days: Optional[int] = 7
    post_window_days: Optional[int] = 7
    post_imagery_open: Optional[bool] = True
    imagery_check_count: Optional[int] = 0

    class Config:
        from_attributes = True


class EventDetail(EventSummary):
    address: Optional[str]
    details_json: Optional[Any]
    source_url: Optional[str]
    pre_image_path: Optional[str]
    pre_image_date: Optional[int]
    pre_image_source: Optional[str]
    post_image_path: Optional[str]
    post_image_date: Optional[int]
    post_image_source: Optional[str]
    quality_score: Optional[float]
    quality_assessment: Optional[Any]
    quality_checked: bool
    quality_check_time: Optional[int]
    # 动态影像追踪（详情专属）
    pre_imagery_exhausted: Optional[bool] = False
    pre_imagery_last_check: Optional[int] = None
    post_imagery_last_check: Optional[int] = None


class EventListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[EventSummary]


class EventStatsResponse(BaseModel):
    total_events: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    by_severity: Dict[str, int]
    recent_24h: int
    by_imagery_status: Optional[Dict[str, int]] = None


# ──────────────────────────────────────────
# Task Queue (GPU Server)
# ──────────────────────────────────────────

class TaskData(BaseModel):
    uuid: str
    pre_image_url: str
    post_image_url: str
    event_details: Dict[str, Any]
    tasks: List[Dict[str, Any]]


class TaskItem(BaseModel):
    id: int
    uuid: str
    priority: int
    task_data: TaskData
    locked_by: Optional[str]
    locked_until: Optional[int]
    created_at: int


class PullTasksResponse(BaseModel):
    tasks: List[TaskItem]
    count: int


class HeartbeatRequest(BaseModel):
    worker_id: str


class HeartbeatResponse(BaseModel):
    message: str
    uuid: str
    heartbeat: int
    locked_until: int


class InferenceTaskResult(BaseModel):
    type: str
    result: Optional[Any]
    error: Optional[str] = None


class SubmitResultRequest(BaseModel):
    worker_id: str
    status: str = "success"
    inference_result: Dict[str, InferenceTaskResult]
    processing_time_seconds: Optional[float] = None
    model_info: Optional[Dict[str, Any]] = None


class SubmitResultResponse(BaseModel):
    message: str
    uuid: str
    status: str
    created: bool


class FailTaskRequest(BaseModel):
    worker_id: str
    reason: str
    error_details: Optional[str] = None
    can_retry: bool = True


class FailTaskResponse(BaseModel):
    message: str
    uuid: str
    retry_count: int
    will_retry: bool


class TaskStatusResponse(BaseModel):
    uuid: str
    status: str
    locked_by: Optional[str]
    locked_at: Optional[int]
    locked_until: Optional[int]
    heartbeat: Optional[int]
    retry_count: int
    created_at: int


# ──────────────────────────────────────────
# Products
# ──────────────────────────────────────────

class ProductSummary(BaseModel):
    uuid: str
    event_title: Optional[str]
    event_category: Optional[str]
    event_country: Optional[str]
    inference_result: Optional[Any]
    summary: Optional[str]
    summary_generated: bool
    created_at: int

    class Config:
        from_attributes = True


class ProductDetail(ProductSummary):
    event_details: Optional[Any]
    pre_image_date: Optional[int]
    post_image_date: Optional[int]
    inference_quality_score: Optional[float]
    summary_generated_at: Optional[int]
    updated_at: int


class ProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[ProductSummary]


# ──────────────────────────────────────────
# Daily Reports
# ──────────────────────────────────────────

class ReportSummary(BaseModel):
    id: int
    report_date: str
    report_title: Optional[str]
    event_count: int
    generated_at: int
    published: bool

    class Config:
        from_attributes = True


class ReportDetail(ReportSummary):
    report_content: str
    category_stats: Optional[Any]
    severity_stats: Optional[Any]
    country_stats: Optional[Any]
    generated_by: Optional[str]
    generation_time_seconds: Optional[float]
    published_at: Optional[int]


class ReportListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[ReportSummary]


class GenerateReportRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class GenerateReportResponse(BaseModel):
    message: str
    report_date: str


# ──────────────────────────────────────────
# Admin
# ──────────────────────────────────────────

class SystemStatusResponse(BaseModel):
    system: Dict[str, Any]
    database: Dict[str, Any]
    gee: Dict[str, Any]
    scheduler: Dict[str, Any]


class CreateTokenRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    scopes: List[str] = ["tasks.read", "tasks.update"]


class CreateTokenResponse(BaseModel):
    token: str
    name: str
    created_at: int


class TokenListItem(BaseModel):
    token: str
    name: str
    description: Optional[str]
    is_active: bool
    usage_count: int
    last_used: Optional[int]
    created_at: int


# ──────────────────────────────────────────
# Common
# ──────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: Optional[int] = None


# ──────────────────────────────────────────
# Event Pool
# ──────────────────────────────────────────

class EventPoolItem(BaseModel):
    event_id: int
    sub_id: int
    title: str
    category: Optional[str]
    category_name: Optional[str]
    country: Optional[str]
    continent: Optional[str]
    severity: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    address: Optional[str]
    event_date: Optional[int]
    last_update: Optional[int]
    first_seen: int
    last_seen: int
    fetch_count: int
    is_active: bool

    class Config:
        from_attributes = True


class EventPoolListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[EventPoolItem]


class EventPoolStatsResponse(BaseModel):
    total_events: int
    active_events: int
    inactive_events: int
    by_category: Dict[str, int]
    by_country: Dict[str, int]
    by_severity: Dict[str, int]
