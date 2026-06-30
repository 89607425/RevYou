import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import Project, ProjectMember
from app.schemas.common import APIResponse
from app.schemas.project import ProjectCreate, ProjectUpdateConfig, TapdTokenRequest

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=APIResponse)
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get project IDs the user is a member of
    member_query = select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.user_id)
    result = await db.execute(member_query)
    project_ids = [row[0] for row in result.all()]

    if not project_ids:
        return APIResponse(data={"total": 0, "items": []})

    # Count total
    count_query = select(func.count()).select_from(Project).where(
        Project.project_id.in_(project_ids), Project.status == "ACTIVE"
    )
    total = (await db.execute(count_query)).scalar()

    # Fetch projects
    offset = (page - 1) * page_size
    proj_query = (
        select(Project)
        .where(Project.project_id.in_(project_ids), Project.status == "ACTIVE")
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    projects = (await db.execute(proj_query)).scalars().all()

    items = []
    for p in projects:
        # Count sessions
        from app.models.review import ReviewSession
        session_count = (await db.execute(
            select(func.count()).select_from(ReviewSession).where(ReviewSession.project_id == p.project_id)
        )).scalar() or 0

        # Count members
        member_count = (await db.execute(
            select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == p.project_id)
        )).scalar() or 0

        items.append({
            "project_id": p.project_id,
            "name": p.name,
            "tapd_project_id": p.tapd_project_id,
            "has_tapd_token": bool(p.tapd_token_encrypted),
            "session_count": session_count,
            "member_count": member_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return APIResponse(data={"total": total, "items": items})


@router.post("", response_model=APIResponse)
async def create_project(
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    default_config = {
        "pm_model": "glm-4",
        "dev_model": "deepseek-v3",
        "qa_model": "qwen-vl-max",
        "text_model": "deepseek-v3",
        "multimodal_model": "glm-4v-plus",
        "auto_switch_model": True,
        "confidence_threshold_low": 0.5,
        "confidence_threshold_high": 0.8,
        "max_review_rounds_deterministic": 1,
        "max_review_rounds_autonomous": 3,
        "max_follow_up_questions": 5,
        "max_issues_per_agent": 30,
        "session_timeout_deterministic_min": 5,
        "session_timeout_autonomous_min": 10,
        "tapd_workspace_id": "37119417",
        "tapd_bug_workspace_id": "38585571",
        "enable_debate": False,
    }

    project = Project(
        project_id=f"PRJ-{uuid.uuid4().hex[:12].upper()}",
        name=req.name,
        tapd_project_id=req.tapd_project_id,
        config=default_config,
        status="ACTIVE",
        created_by=current_user.user_id,
    )
    db.add(project)
    await db.flush()

    # Add creator as admin member
    member = ProjectMember(
        project_id=project.project_id,
        user_id=current_user.user_id,
        role="ADMIN",
    )
    db.add(member)
    await db.commit()

    return APIResponse(data={"project_id": project.project_id, "name": project.name})


@router.get("/{project_id}", response_model=APIResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Get members
    members_result = await db.execute(
        select(ProjectMember, User.display_name)
        .join(User, ProjectMember.user_id == User.user_id)
        .where(ProjectMember.project_id == project_id)
    )
    members = [
        {"user_id": pm.user_id, "display_name": name, "role": pm.role}
        for pm, name in members_result.all()
    ]

    return APIResponse(data={
        "project_id": project.project_id,
        "name": project.name,
        "tapd_project_id": project.tapd_project_id,
        "tapd_api_user": project.tapd_api_user or "",
        "has_tapd_token": bool(project.tapd_token_encrypted),
        "config": project.config,
        "members": members,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    })


@router.put("/{project_id}/config", response_model=APIResponse)
async def update_project_config(
    project_id: str,
    req: ProjectUpdateConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can update config")

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    update_data = req.model_dump(exclude_unset=True)
    config = dict(project.config or {})
    config.update(update_data)
    project.config = config
    await db.commit()

    return APIResponse(data={"message": "Config updated"})


@router.put("/{project_id}/tapd-token", response_model=APIResponse)
async def set_tapd_token(
    project_id: str,
    req: TapdTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can configure TAPD token")

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    from app.core.security import hash_password
    project.tapd_api_user = req.tapd_api_user
    project.tapd_token_encrypted = req.tapd_token
    await db.commit()

    return APIResponse(data={"valid": True, "message": "Token saved"})
