import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.review import ReviewSession, ReviewIssue

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("")
async def create_session(
    project_id: str,
    agent_mode: str,
    prd_source: str,
    prd_text: str = None,
    prd_files: list = None,
    tapd_story_id: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a review session. Simplified MVP stub - will be fully implemented in Phase 3."""
    session_id = f"SES-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    session = ReviewSession(
        session_id=session_id,
        project_id=project_id,
        prd_content=prd_text or "",
        prd_source=prd_source,
        prd_structure={"sections": [], "total_sections": 0, "total_chars": len(prd_text or "")},
        prd_images=[],
        tapd_story_id=tapd_story_id,
        agent_mode=agent_mode,
        status="RUNNING",
        initiator_id=current_user.user_id,
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "code": 0,
        "data": {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "status": session.status,
            "agent_mode": session.agent_mode,
            "prd_source": session.prd_source,
            "prd_structure": session.prd_structure,
            "prd_images": session.prd_images,
            "tapd_story_id": session.tapd_story_id,
            "initiator_id": session.initiator_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "estimated_completion": None,
        },
    }


@router.get("")
async def list_sessions(
    project_id: str = Query(...),
    status: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ReviewSession).where(ReviewSession.project_id == project_id)
    if status and status != "ALL":
        query = query.where(ReviewSession.status == status)

    count_query = select(func.count()).select_from(ReviewSession).where(ReviewSession.project_id == project_id)
    if status and status != "ALL":
        count_query = count_query.where(ReviewSession.status == status)

    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    sessions = (await db.execute(
        query.order_by(ReviewSession.created_at.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    items = []
    for s in sessions:
        # Count issues by severity
        issue_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0}
        if s.status in ("COMPLETED", "TIMEOUT"):
            high_count = (await db.execute(
                select(func.count()).select_from(ReviewIssue).where(
                    ReviewIssue.session_id == s.session_id, ReviewIssue.severity == "HIGH"
                )
            )).scalar() or 0
            med_count = (await db.execute(
                select(func.count()).select_from(ReviewIssue).where(
                    ReviewIssue.session_id == s.session_id, ReviewIssue.severity == "MEDIUM"
                )
            )).scalar() or 0
            low_count = (await db.execute(
                select(func.count()).select_from(ReviewIssue).where(
                    ReviewIssue.session_id == s.session_id, ReviewIssue.severity == "LOW"
                )
            )).scalar() or 0
            issue_counts = {"HIGH": high_count, "MEDIUM": med_count, "LOW": low_count, "total": high_count + med_count + low_count}

        # Get initiator name
        initiator_result = await db.execute(select(User.display_name).where(User.user_id == s.initiator_id))
        initiator_name = initiator_result.scalar_one_or_none()

        items.append({
            "session_id": s.session_id,
            "project_id": s.project_id,
            "status": s.status,
            "agent_mode": s.agent_mode,
            "prd_source": s.prd_source,
            "issue_count": issue_counts,
            "initiator": {"user_id": s.initiator_id, "display_name": initiator_name},
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        })

    return {"code": 0, "data": {"total": total, "items": items}}


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ReviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return {
        "code": 0,
        "data": {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "status": session.status,
            "agent_mode": session.agent_mode,
            "prd_source": session.prd_source,
            "prd_structure": session.prd_structure,
            "prd_images": session.prd_images,
            "tapd_story_id": session.tapd_story_id,
            "initiator_id": session.initiator_id,
            "agent_results": session.agent_results,
            "agent_progress": [],
            "follow_up_questions": session.follow_up_questions or [],
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        },
    }


@router.post("/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ReviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status != "RUNNING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not running")

    session.status = "CANCELLED"
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()

    # Count existing issues
    issue_count = (await db.execute(
        select(func.count()).select_from(ReviewIssue).where(ReviewIssue.session_id == session_id)
    )).scalar() or 0

    return {"code": 0, "data": {"session_id": session_id, "status": "CANCELLED", "partial_results_available": issue_count > 0, "issue_count": issue_count}}
