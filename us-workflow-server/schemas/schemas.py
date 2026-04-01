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
    scheduler_enabled: bool
    legacy_root: str
    database_path: str


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
    updated_at: Optional[int]


class WorkflowItemListResponse(BaseModel):
    total: int
    data: List[WorkflowItemResponse]


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
