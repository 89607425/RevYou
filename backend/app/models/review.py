"""Review data models — ReviewPlan, ReflectResult, Issue, Agent reports, etc."""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class Severity(str, Enum):
    critical = "critical"
    major = "major"
    minor = "minor"
    suggestion = "suggestion"


class Issue(BaseModel):
    id: str = ""
    severity: Severity = Severity.minor
    location: str = ""
    title: str = ""
    description: str = ""
    suggestion: str = ""


# ─── Step 1: ReviewPlan (autonomous planning) ───────────────────────────

class DocumentAnalysis(BaseModel):
    doc_type: str = Field(description="UI / data / API / business logic / etc.")
    complexity_score: int = Field(ge=1, le=5)
    key_observation: str = ""


class RiskArea(BaseModel):
    area: str
    reason: str
    evidence_location: str = ""


class FocusArea(BaseModel):
    area: str
    questions: list[str] = Field(default_factory=list)
    related_sections: list[str] = Field(default_factory=list)


class ReviewPlan(BaseModel):
    document_analysis: DocumentAnalysis
    risk_areas: list[RiskArea] = Field(default_factory=list)
    focus_areas: list[FocusArea] = Field(default_factory=list)
    depth_assessment: int = Field(ge=1, le=3, default=1)


# ─── Step 3: ReflectResult (self-assessment) ─────────────────────────────

class ReflectResult(BaseModel):
    coverage_gaps: list[str] = Field(default_factory=list)
    quality_issues: list[str] = Field(default_factory=list,
        description="IDs of findings that are too vague or lack evidence")
    false_positives: list[str] = Field(default_factory=list,
        description="IDs of findings suspected of over-flagging")
    needs_another_pass: bool = False
    gap_areas: list[str] = Field(default_factory=list,
        description="Areas that need re-review if needs_another_pass is True")


# ─── Step 2 output: raw findings ────────────────────────────────────────

class FocusAreaFindings(BaseModel):
    area: str
    issues: list[Issue] = Field(default_factory=list)
    notes: str = ""


# ─── Phase 1 final output ───────────────────────────────────────────────

class AgentPhase1Report(BaseModel):
    role: str
    overall_score: int = 0
    verdict: str = ""
    highlights: list[str] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    # thinking trace
    review_plan: Optional[ReviewPlan] = None
    reflect_result: Optional[ReflectResult] = None
    call_count: int = 0


# ─── Phase 2 (cross-review) models ──────────────────────────────────────

class CrossReviewPlan(BaseModel):
    peer_insight_analysis: list[str] = Field(default_factory=list,
        description="What blind spots did peer findings reveal?")
    re_review_targets: list[str] = Field(default_factory=list,
        description="Document areas to re-review based on peer findings")
    my_weakness_check: list[str] = Field(default_factory=list,
        description="Own conclusions that might be challenged")


class PeerOpinion(BaseModel):
    peer_issue_id: str
    comment: str = ""


class SeverityAdjust(BaseModel):
    issue_id: str
    from_severity: Severity
    to_severity: Severity
    reason: str


class AgentPhase2Report(BaseModel):
    role: str
    peer_agreements: list[PeerOpinion] = Field(default_factory=list)
    peer_disagreements: list[PeerOpinion] = Field(default_factory=list)
    new_issues: list[Issue] = Field(default_factory=list)
    severity_adjustments: list[SeverityAdjust] = Field(default_factory=list)
    # thinking trace
    cross_review_plan: Optional[CrossReviewPlan] = None
    call_count: int = 0


# ─── Aggregated report ──────────────────────────────────────────────────

class Summary(BaseModel):
    overall_score: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    role_counts: dict[str, int] = Field(default_factory=dict)
    top_risks: list[Issue] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    readiness_verdict: str = ""


class CrossReviewSummary(BaseModel):
    agreements: int = 0
    disagreements: int = 0
    typical_disagreements: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    job_id: str
    document_title: str
    source_type: str
    summary: Summary = Field(default_factory=Summary)
    agents: dict[str, AgentPhase1Report] = Field(default_factory=dict)
    cross_review: dict[str, AgentPhase2Report] = Field(default_factory=dict)
    cross_summary: CrossReviewSummary = Field(default_factory=CrossReviewSummary)


# ─── Job state ──────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    queued = "queued"
    parsing = "parsing"
    phase1 = "phase1"
    phase2 = "phase2"
    aggregating = "aggregating"
    done = "done"
    failed = "failed"


class ThinkingStep(BaseModel):
    """One step in the agent's thinking trajectory, for SSE + persistence."""
    agent_role: str
    phase: str = Field(description="phase1 or phase2")
    step: str = Field(description="plan / execute / reflect / adjust / consolidate")
    focus_area: str = ""
    raw_output: str = ""
    timestamp: str = ""
