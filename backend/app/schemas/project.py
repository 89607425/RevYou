from typing import Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProjectConfig(BaseModel):
    text_model: str = "deepseek-v3"
    multimodal_model: str = "qwen-vl-max"
    auto_switch_model: bool = True
    confidence_threshold_low: float = 0.5
    confidence_threshold_high: float = 0.8
    max_review_rounds_deterministic: int = 1
    max_review_rounds_autonomous: int = 3
    max_follow_up_questions: int = 5
    max_issues_per_agent: int = 30
    session_timeout_deterministic_min: int = 5
    session_timeout_autonomous_min: int = 10


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    tapd_project_id: Optional[str] = None


class ProjectUpdateConfig(BaseModel):
    text_model: Optional[str] = None
    multimodal_model: Optional[str] = None
    auto_switch_model: Optional[bool] = None
    confidence_threshold_low: Optional[float] = None
    confidence_threshold_high: Optional[float] = None
    max_review_rounds_deterministic: Optional[int] = None
    max_review_rounds_autonomous: Optional[int] = None
    max_follow_up_questions: Optional[int] = None


class TapdTokenRequest(BaseModel):
    tapd_token: str


class ProjectMemberInfo(BaseModel):
    user_id: str
    display_name: str
    role: str


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    tapd_project_id: Optional[str] = None
    has_tapd_token: bool = False
    session_count: int = 0
    member_count: int = 0
    created_at: Optional[datetime] = None
