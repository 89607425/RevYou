"""TAPD integration API routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.services.tapd_service import TapdService

router = APIRouter(prefix="/tapd", tags=["tapd"])


@router.get("/validate")
async def validate_token(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate TAPD API token and list accessible workspaces."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not project.tapd_token_encrypted:
        return {"code": 0, "data": {"valid": False, "message": "请先配置TAPD令牌"}}

    config = project.config or {}
    tapd = TapdService(
        api_token=project.tapd_token_encrypted,
        workspace_id=config.get("tapd_workspace_id"),
    )
    result = await tapd.validate_token()
    return {"code": 0, "data": result}


@router.get("/stories/search")
async def search_stories(
    project_id: str = Query(...),
    keyword: str = Query(default=None),
    story_id: str = Query(default=None),
    tapd_workspace_id: str = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search TAPD stories."""
    project = await db.get(Project, project_id)
    if not project or not project.tapd_token_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目未配置TAPD令牌")

    tapd = TapdService(api_token=project.tapd_token_encrypted, workspace_id=tapd_workspace_id)
    stories = await tapd.search_stories(keyword=keyword, story_id=story_id)
    return {"code": 0, "data": {"items": stories, "total": len(stories)}}


@router.get("/story-preview")
async def preview_story(
    project_id: str = Query(...),
    story_id: str = Query(...),
    tapd_workspace_id: str = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview a TAPD story's full composed PRD without creating a session."""
    project = await db.get(Project, project_id)
    if not project or not project.tapd_token_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目未配置TAPD令牌")

    config = project.config or {}
    bug_ws = config.get("tapd_bug_workspace_id") if config else None
    tapd = TapdService(api_token=project.tapd_token_encrypted, workspace_id=tapd_workspace_id, bug_workspace_id=bug_ws)
    result = await tapd.compose_full_prd(story_id)

    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    return {"code": 0, "data": {
        "story": result["story"],
        "stats": result["stats"],
        "prd_text_preview": result["prd_text"][:2000] + ("..." if len(result["prd_text"]) > 2000 else ""),
        "total_chars": len(result["prd_text"]),
    }}
