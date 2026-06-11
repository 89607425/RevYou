"""Dashboard API: project risk dashboard and statistics."""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.review import ReviewSession, ReviewIssue

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/risk-dashboard")
async def get_risk_dashboard(
    project_id: str,
    period: str = Query(default="30d"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Calculate time range
    now = datetime.now(timezone.utc)
    if period == "7d":
        since = now - timedelta(days=7)
    elif period == "30d":
        since = now - timedelta(days=30)
    else:
        since = None

    # Get sessions for project
    session_query = select(ReviewSession).where(ReviewSession.project_id == project_id)
    if since:
        session_query = session_query.where(ReviewSession.created_at >= since)
    session_result = await db.execute(session_query)
    sessions = session_result.scalars().all()
    session_ids = [s.session_id for s in sessions]

    total_sessions = len(sessions)

    # Get issues for these sessions
    if session_ids:
        issue_query = select(ReviewIssue).where(ReviewIssue.session_id.in_(session_ids))
        issue_result = await db.execute(issue_query)
        issues = issue_result.scalars().all()
    else:
        issues = []

    total_issues = len(issues)
    open_issues = sum(1 for i in issues if i.status == "OPEN")
    high_open = sum(1 for i in issues if i.status == "OPEN" and i.severity == "HIGH")
    avg_issues = round(total_issues / total_sessions, 1) if total_sessions else 0

    # Severity distribution
    severity_dist = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for i in issues:
        severity_dist[i.severity] += 1

    # Issue type distribution
    type_dist = {"TECHNICAL_RISK": 0, "LOGIC_GAP": 0, "TEST_MISSING": 0, "DATA_INCONSISTENCY": 0}
    for i in issues:
        if i.issue_type in type_dist:
            type_dist[i.issue_type] += 1

    # Agent distribution
    agent_dist = {"PM_REVIEW": 0, "DEV_REVIEW": 0, "QA_REVIEW": 0}
    for i in issues:
        if i.source_agent in agent_dist:
            agent_dist[i.source_agent] += 1

    # Recent high severity (top 10)
    high_issues = sorted(
        [i for i in issues if i.severity == "HIGH"],
        key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:10]

    return {
        "code": 0,
        "data": {
            "summary": {
                "total_sessions": total_sessions,
                "total_issues": total_issues,
                "open_issues": open_issues,
                "high_severity_open": high_open,
                "avg_issues_per_session": avg_issues,
            },
            "severity_distribution": severity_dist,
            "issue_type_distribution": type_dist,
            "agent_issue_distribution": agent_dist,
            "trend": [],
            "recent_high_severity": [
                {
                    "issue_id": i.issue_id,
                    "title": i.title,
                    "session_id": i.session_id,
                    "status": i.status,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in high_issues
            ],
        },
    }
