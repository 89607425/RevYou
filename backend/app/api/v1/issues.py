from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.review import ReviewSession, ReviewIssue, IssueComment

router = APIRouter(tags=["issues"])


@router.get("/sessions/{session_id}/issues")
async def list_issues(
    session_id: str,
    source_agent: str = Query(default=None),
    severity: str = Query(default=None),
    status_filter: str = Query(default=None, alias="status"),
    confidence_min: float = Query(default=0.0, ge=0.0, le=1.0),
    section_id: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="severity"),
    sort_order: str = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ReviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    query = select(ReviewIssue).where(ReviewIssue.session_id == session_id)
    count_base = select(func.count()).select_from(ReviewIssue).where(ReviewIssue.session_id == session_id)

    if source_agent:
        query = query.where(ReviewIssue.source_agent == source_agent)
        count_base = count_base.where(ReviewIssue.source_agent == source_agent)
    if severity:
        query = query.where(ReviewIssue.severity == severity)
        count_base = count_base.where(ReviewIssue.severity == severity)
    if status_filter:
        query = query.where(ReviewIssue.status == status_filter)
        count_base = count_base.where(ReviewIssue.status == status_filter)
    if confidence_min > 0:
        query = query.where(ReviewIssue.confidence >= confidence_min)
        count_base = count_base.where(ReviewIssue.confidence >= confidence_min)

    total = (await db.execute(count_base)).scalar() or 0

    # Sort
    sort_col = ReviewIssue.created_at
    if sort_by == "severity":
        sort_col = ReviewIssue.severity
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    issues = result.scalars().all()

    items = [{
        "issue_id": i.issue_id,
        "session_id": i.session_id,
        "source_agent": i.source_agent,
        "issue_type": i.issue_type,
        "severity": i.severity,
        "title": i.title,
        "description": i.description,
        "suggestion": i.suggestion,
        "prd_section": i.prd_section,
        "prd_quote": i.prd_quote,
        "image_ref": i.image_ref,
        "confidence": float(i.confidence) if i.confidence else None,
        "confidence_label": i.confidence_label,
        "status": i.status,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    } for i in issues]

    return {"code": 0, "data": {"total": total, "items": items}}


@router.patch("/sessions/{session_id}/issues/{issue_id}")
async def update_issue(
    session_id: str,
    issue_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await db.get(ReviewIssue, issue_id)
    if not issue or issue.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    new_status = body.get("status")
    if new_status == "FALSE_POSITIVE" and not body.get("resolution_note"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="resolution_note is required for FALSE_POSITIVE")
    if new_status == "RESOLVED" and not body.get("resolution_note"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="resolution_note is required for RESOLVED")

    issue.status = new_status
    if body.get("resolution_note"):
        issue.resolution_note = body["resolution_note"]
    if new_status in ("CONFIRMED", "RESOLVED"):
        issue.resolved_by = current_user.user_id

    issue.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(issue)

    return {"code": 0, "data": {
        "issue_id": issue.issue_id,
        "status": issue.status,
        "resolution_note": issue.resolution_note,
    }}


@router.patch("/sessions/{session_id}/issues/{issue_id}/severity")
async def update_issue_severity(
    session_id: str,
    issue_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await db.get(ReviewIssue, issue_id)
    if not issue or issue.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    new_severity = body.get("severity")
    if new_severity not in ("HIGH", "MEDIUM", "LOW"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid severity")

    issue.severity = new_severity
    issue.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"code": 0, "data": {"issue_id": issue_id, "severity": new_severity}}


@router.post("/sessions/{session_id}/issues/{issue_id}/comments")
async def create_comment(
    session_id: str,
    issue_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await db.get(ReviewIssue, issue_id)
    if not issue or issue.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    import uuid
    comment = IssueComment(
        comment_id=f"CMT-{uuid.uuid4().hex[:12].upper()}",
        issue_id=issue_id,
        user_id=current_user.user_id,
        content=body.get("content", ""),
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return {"code": 0, "data": {
        "comment_id": comment.comment_id,
        "issue_id": issue_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }}


@router.get("/sessions/{session_id}/issues/{issue_id}/comments")
async def list_comments(
    session_id: str,
    issue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IssueComment, User.display_name, User.role)
        .join(User, IssueComment.user_id == User.user_id)
        .where(IssueComment.issue_id == issue_id)
        .order_by(IssueComment.created_at.asc())
    )
    items = [
        {
            "comment_id": c.comment_id,
            "user_id": c.user_id,
            "display_name": name,
            "role": role,
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c, name, role in result.all()
    ]
    return {"code": 0, "data": {"items": items}}


@router.get("/sessions/{session_id}/issues/{issue_id}/copy")
async def copy_issue_text(
    session_id: str,
    issue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await db.get(ReviewIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    copy_text = f"【AI审查】{issue.title}\n\n问题描述：{issue.description}\n\n建议方案：{issue.suggestion or '无'}\n\n严重等级：{issue.severity} | 置信度：{issue.confidence} | 来源：{issue.source_agent}"

    return {"code": 0, "data": {"copy_text": copy_text}}
