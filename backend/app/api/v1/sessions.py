import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db, async_session_factory
from app.core.security import get_current_user
from app.models.user import User
from app.models.review import ReviewSession, ReviewIssue
from app.services.tapd_service import TapdService
from app.services.prd_parser import parse_prd_structure, parse_pdf, parse_docx, validate_file
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    project_id: str
    agent_mode: str = "DETERMINISTIC"
    prd_source: str = "TEXT"
    prd_text: Optional[str] = None
    tapd_story_id: Optional[str] = None
    tapd_workspace_id: Optional[str] = None


@router.post("")
async def create_session(
    req: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a review session with PRD content from TEXT, TAPD, or uploaded file."""
    session_id = f"SES-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    prd_content = ""
    prd_structure = {"sections": [], "total_sections": 0, "total_chars": 0}
    prd_images = []
    tapd_story_id = None
    tapd_import_stats = None

    if req.prd_source == "TEXT":
        if not req.prd_text or not req.prd_text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PRD内容不能为空")
        prd_content = req.prd_text.strip()
        prd_structure = parse_prd_structure(prd_content)

    elif req.prd_source == "TAPD":
        if not req.tapd_story_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TAPD需求ID不能为空")
        tapd_story_id = req.tapd_story_id

        tapd_token = None
        from app.models.project import Project
        project = await db.get(Project, req.project_id)
        if project and project.tapd_token_encrypted:
            tapd_token = project.tapd_token_encrypted

        if not tapd_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目未配置TAPD令牌，请先在项目设置中配置")

        config = project.config or {}
        bug_ws = config.get("tapd_bug_workspace_id") if config else None
        tapd = TapdService(api_token=tapd_token, workspace_id=req.tapd_workspace_id, bug_workspace_id=bug_ws)
        result = await tapd.compose_full_prd(req.tapd_story_id)

        if result.get("error"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

        prd_content = result["prd_text"]
        tapd_import_stats = result.get("stats", {})
        prd_structure = parse_prd_structure(prd_content)

        if not prd_content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法从TAPD获取需求内容")

    elif req.prd_source == "FILE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件上传请使用 /sessions/upload 接口")

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的需求来源: {req.prd_source}")

    session = ReviewSession(
        session_id=session_id,
        project_id=req.project_id,
        prd_content=prd_content,
        prd_source=req.prd_source,
        prd_structure=prd_structure,
        prd_images=prd_images,
        tapd_story_id=tapd_story_id,
        agent_mode=req.agent_mode,
        status="RUNNING",
        initiator_id=current_user.user_id,
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    response_data = {
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
    }
    if tapd_import_stats:
        response_data["tapd_import_stats"] = tapd_import_stats

    import asyncio
    asyncio.create_task(_run_review_async(session_id, req.project_id))

    return {"code": 0, "data": response_data}


@router.post("/upload")
async def upload_prd_file(
    project_id: str = Form(...),
    agent_mode: str = Form(default="DETERMINISTIC"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a review session from an uploaded PRD file (PDF/DOCX)."""
    content = await file.read()

    error_msg = validate_file(file.filename, len(content))
    if error_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    filename_lower = file.filename.lower()
    if filename_lower.endswith(".pdf"):
        prd_content = parse_pdf(content)
    elif filename_lower.endswith(".docx"):
        prd_content = parse_docx(content)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的文件格式，请上传 PDF 或 DOCX 文件")

    if not prd_content or not prd_content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法从文件中提取文本内容")

    session_id = f"SES-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    prd_structure = parse_prd_structure(prd_content)

    session = ReviewSession(
        session_id=session_id,
        project_id=project_id,
        prd_content=prd_content,
        prd_source="FILE",
        prd_structure=prd_structure,
        prd_images=[],
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

    import asyncio
    asyncio.create_task(_run_review_async(session_id, project_id))

    return {
        "code": 0,
        "data": {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "status": session.status,
            "agent_mode": session.agent_mode,
            "prd_source": session.prd_source,
            "prd_structure": session.prd_structure,
            "initiator_id": session.initiator_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "filename": file.filename,
        },
    }


@router.get("")
async def list_sessions(
    project_id: str = Query(...),
    status_param: str = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ReviewSession).where(ReviewSession.project_id == project_id)
    if status_param and status_param != "ALL":
        query = query.where(ReviewSession.status == status_param)

    count_query = select(func.count()).select_from(ReviewSession).where(ReviewSession.project_id == project_id)
    if status_param and status_param != "ALL":
        count_query = count_query.where(ReviewSession.status == status_param)

    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    sessions = (await db.execute(
        query.order_by(ReviewSession.created_at.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    items = []
    for s in sessions:
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
            "prd_content": session.prd_content,
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

    issue_count = (await db.execute(
        select(func.count()).select_from(ReviewIssue).where(ReviewIssue.session_id == session_id)
    )).scalar() or 0

    return {"code": 0, "data": {"session_id": session_id, "status": "CANCELLED", "partial_results_available": issue_count > 0, "issue_count": issue_count}}


class AnswerFollowUpRequest(BaseModel):
    answers: list[dict]
    action: str = "CONTINUE"

@router.post("/{session_id}/answer")
async def answer_follow_up(
    session_id: str,
    req: AnswerFollowUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer agent follow-up questions and resume autonomous review."""
    session = await db.get(ReviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status not in ("RUNNING", "AWAITING_USER"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                           detail=f"Session is not awaiting user input (current status: {session.status})")

    existing_follow_ups = session.follow_up_questions or []
    if isinstance(existing_follow_ups, list):
        existing_follow_ups.extend(req.answers)
    else:
        existing_follow_ups = req.answers
    session.follow_up_questions = existing_follow_ups
    await db.commit()

    if req.action == "SKIP":
        session.status = "COMPLETED"
        session.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await ws_manager.broadcast_session_completed(session_id, {"total": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0})
        return {"code": 0, "data": {"session_id": session_id, "status": "COMPLETED", "message": "审核结束（用户跳过追问）"}}

    if req.action == "CONTINUE":
        session.status = "RUNNING"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        import asyncio
        asyncio.create_task(_run_review_async(session_id, session.project_id, user_answers=req.answers))
        return {"code": 0, "data": {"session_id": session_id, "status": "RUNNING", "message": "已收到回答，继续审查..."}}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"未知操作: {req.action}")


async def _run_review_async(session_id: str, project_id: str, user_answers: list = None):
    """Background task to run the AI agent review."""
    import traceback
    try:
        async with async_session_factory() as db:
            session = await db.get(ReviewSession, session_id)
            if not session:
                return

            from app.services.agent_engine import run_review
            from app.models.project import Project
            project = await db.get(Project, project_id)

            config = {}
            if project:
                config = project.config or {}
                config["tapd_token"] = project.tapd_token_encrypted or ""

            await ws_manager.broadcast_progress(session_id, "SYSTEM", 0.0)
            await ws_manager.send_message(session_id, "AGENT_THINKING", {
                "agent": "SYSTEM",
                "message": "正在启动 AI Agent 审查...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            result = await run_review(
                prd_content=session.prd_content,
                agent_mode=session.agent_mode,
                config=config,
                session_id=session_id,
                project_id=project_id,
                ws_manager=ws_manager,
                user_answers=user_answers or [],
            )

            issues = result.get("final_issues", result.get("issues", []))
            agent_results = result.get("agent_results", {})

            debate_mode = config.get("enable_debate", False)
            for issue_data in issues:
                conf = float(issue_data.get("confidence", 0.8))
                if conf >= 0.8:
                    clabel = "HIGH"
                elif conf >= 0.5:
                    clabel = "MEDIUM"
                else:
                    clabel = "LOW"

                issue = ReviewIssue(
                    issue_id=f"ISS-{uuid.uuid4().hex[:12].upper()}",
                    session_id=session_id,
                    source_agent=issue_data.get("source_agent", "UNKNOWN"),
                    issue_type=issue_data.get("issue_type", "LOGIC_GAP"),
                    severity=issue_data.get("severity", "MEDIUM"),
                    title=issue_data.get("title", "未命名问题"),
                    description=issue_data.get("description", ""),
                    suggestion=issue_data.get("suggestion"),
                    prd_section=issue_data.get("prd_section"),
                    prd_quote=issue_data.get("prd_quote"),
                    confidence=conf,
                    confidence_label=clabel,
                    cross_review_tags=issue_data.get("cross_review_tags", []) if debate_mode else None,
                    status="OPEN",
                    review_round=user_answers.get("round", 1) if isinstance(user_answers, dict) else 1,
                )
                db.add(issue)
                await db.flush()

                issue_dict = {
                    "issue_id": issue.issue_id,
                    "source_agent": issue.source_agent,
                    "severity": issue.severity,
                    "title": issue.title,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "prd_section": issue.prd_section,
                    "confidence": float(issue.confidence),
                    "confidence_label": issue.confidence_label,
                    "status": issue.status,
                }
                await ws_manager.broadcast_issue(session_id, issue_dict)

            session.agent_results = agent_results

            follow_up_questions = result.get("follow_ups", [])
            if isinstance(follow_up_questions, list) and follow_up_questions:
                follow_up_questions = follow_up_questions

            all_follow_ups = session.follow_up_questions or []
            if isinstance(all_follow_ups, dict):
                all_follow_ups = []
            if isinstance(follow_up_questions, list):
                all_follow_ups = list(all_follow_ups) + follow_up_questions
            session.follow_up_questions = all_follow_ups

            is_autonomous = session.agent_mode == "AUTONOMOUS"
            max_rounds = config.get("max_review_rounds_autonomous", 3)
            current_round = len([a for a in all_follow_ups if isinstance(a, dict) and a.get("answered")]) + 1

            if is_autonomous and follow_up_questions and isinstance(follow_up_questions, list) and len(follow_up_questions) > 0 and current_round < max_rounds:
                session.status = "AWAITING_USER"
                session.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await ws_manager.broadcast_awaiting_answer(
                    session_id,
                    follow_up_questions,
                    current_round,
                    max_rounds,
                )
                await ws_manager.send_message(session_id, "AGENT_THINKING", {
                    "agent": "SYSTEM",
                    "message": f"审查第{current_round}轮完成，Agent 有 {len(follow_up_questions)} 个追问等待您回答",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return

            session.status = "COMPLETED"
            session.completed_at = datetime.now(timezone.utc)
            await db.commit()

            issue_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": len(issues)}
            for i in issues:
                sev = i.get("severity", "MEDIUM")
                if sev in issue_counts:
                    issue_counts[sev] += 1

            await ws_manager.broadcast_session_completed(session_id, issue_counts)
            await ws_manager.send_message(session_id, "AGENT_THINKING", {
                "agent": "SYSTEM",
                "message": f"审查完成！共发现 {len(issues)} 个问题。",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    except Exception as e:
        logger.error(f"Review failed for session {session_id}: {e}\n{traceback.format_exc()}")
        try:
            async with async_session_factory() as db:
                session = await db.get(ReviewSession, session_id)
                if session:
                    session.status = "TIMEOUT"
                    session.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            await ws_manager.broadcast_session_timeout(session_id, 0)
            await ws_manager.send_message(session_id, "AGENT_THINKING", {
                "agent": "SYSTEM",
                "message": f"审查出错: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except:
            pass
