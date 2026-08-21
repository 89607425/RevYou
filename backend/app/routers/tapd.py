"""TAPD router — story search and preview."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..services.tapd_adapter import tapd_adapter

router = APIRouter(prefix="/api/tapd", tags=["tapd"])


class TapdFetchRequest(BaseModel):
    workspace_id: str
    story_id: str


@router.get("/stories/search")
async def search_stories(workspace_id: str = "", keyword: str = "", limit: int = 20):
    """Search stories in a TAPD workspace."""
    ws = workspace_id or settings.tapd_workspace_ids.split(",")[0].strip()
    if not ws:
        raise HTTPException(400, "workspace_id is required (or set TAPD_WORKSPACE_IDS)")
    try:
        stories = await tapd_adapter.search_stories(ws, keyword, limit)
        return {"stories": stories}
    except Exception as e:
        raise HTTPException(502, f"TAPD API error: {e}")


@router.post("/stories/fetch")
async def fetch_story(request: TapdFetchRequest):
    """Fetch and preview a single story."""
    try:
        story = await tapd_adapter.get_story(request.workspace_id, request.story_id)
        if not story:
            raise HTTPException(404, f"Story {request.story_id} not found")
        return {"story": story}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"TAPD API error: {e}")
