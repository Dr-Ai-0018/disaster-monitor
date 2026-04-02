from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class WorkflowOverviewCard(BaseModel):
    key: str
    label: str
    total: int
    auto_mode: str
    description: str


class WorkflowOverviewResponse(BaseModel):
    cards: List[WorkflowOverviewCard]
    service_status: str
    automation_scope: str
    review_scope: str


class WorkflowItemResponse(BaseModel):
    uuid: str
    title: Optional[str]
    country: Optional[str]
    severity: Optional[str]
    event_status: Optional[str]
    pool: str
    imagery: str
    quality: str
    inference: str
    summary: str
    report_candidate: str
    pool_status: str
    event_date: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    selected_image_type: Optional[str]
    last_operator: Optional[str]
    updated_at: Optional[int]


class WorkflowItemListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[WorkflowItemResponse]


class WorkflowSelectionResponse(BaseModel):
    total: int
    uuids: List[str]


class WorkflowItemDetailResponse(WorkflowItemResponse):
    category: Optional[str]
    address: Optional[str]
    detail_fetch_status: Optional[str]
    pre_image_path: Optional[str]
    post_image_path: Optional[str]
    task_status: Optional[str]
    task_progress_stage: Optional[str]
    task_progress_message: Optional[str]
    task_failure_reason: Optional[str]
    summary_text: Optional[str]
    summary_review_status: Optional[str]
    summary_review_reason: Optional[str]
    report_date: Optional[str]
    report_ready: bool


class ResetResponse(BaseModel):
    message: str
    affected: int


class SummaryApprovalRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None
    report_date: Optional[str] = None


class ImageReviewDecisionRequest(BaseModel):
    approved: bool
    image_type: Optional[str] = None
    reason: Optional[str] = None


class BatchUuidRequest(BaseModel):
    uuids: List[str]


class StageResetRequest(BaseModel):
    stage: str


class BatchStageResetRequest(BaseModel):
    uuids: List[str]
    stage: str


class BatchPreviousPoolRollbackRequest(BaseModel):
    uuids: List[str]


class BatchImageReviewRequest(BaseModel):
    uuids: List[str]
    approved: bool
    image_type: Optional[str] = None
    reason: Optional[str] = None


class BatchSummaryApprovalRequest(BaseModel):
    uuids: List[str]
    approved: bool
    reason: Optional[str] = None
    report_date: Optional[str] = None


class InferenceTriggerRequest(BaseModel):
    selected_image_type: Optional[str] = None


class BatchInferenceTriggerRequest(BaseModel):
    uuids: List[str]
    selected_image_type: Optional[str] = None


class SummaryGenerateRequest(BaseModel):
    persist: bool = True


class BatchSummaryGenerateRequest(BaseModel):
    uuids: List[str]
    persist: bool = True


class ReportGenerateRequest(BaseModel):
    report_date: str


class ReportCandidateResponse(BaseModel):
    uuid: str
    title: Optional[str]
    country: Optional[str]
    severity: Optional[str]
    report_date: str
    updated_at: Optional[int]


class ReportCandidateListResponse(BaseModel):
    total: int
    data: List[ReportCandidateResponse]


class ReportGenerateResponse(BaseModel):
    message: str
    report_date: str
    report_title: Optional[str]
    event_count: int
    published: bool


class ReportSummaryResponse(BaseModel):
    report_date: str
    report_title: Optional[str]
    event_count: int
    generated_at: Optional[int]
    published: bool


class ReportSummaryListResponse(BaseModel):
    total: int
    data: List[ReportSummaryResponse]


class ReportDetailResponse(ReportSummaryResponse):
    report_content: str
    category_stats: Optional[str] = None
    severity_stats: Optional[str] = None
    country_stats: Optional[str] = None
    published_at: Optional[int] = None


class BatchItemResult(BaseModel):
    uuid: str
    ok: bool
    message: str


class BatchActionResponse(BaseModel):
    message: str
    total: int
    succeeded: int
    failed: int
    results: List[BatchItemResult]
