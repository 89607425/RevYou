"""TAPD read-only integration service."""
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class TapdService:
    """Service for TAPD read-only API integration."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = settings.TAPD_API_BASE

    def _headers(self) -> dict:
        return {
            "Authorization": f"Basic {self.api_token}",
            "Content-Type": "application/json",
        }

    async def validate_token(self) -> dict:
        """Validate TAPD API token connectivity."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/workspaces/users",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return {"valid": True, "message": "Token valid"}
                return {"valid": False, "message": f"API returned {resp.status_code}"}
        except Exception as e:
            return {"valid": False, "message": str(e)}

    async def get_story(self, story_id: str) -> Optional[dict]:
        """Fetch a TAPD story by ID."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/stories",
                    params={"id": story_id},
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    stories = data.get("data", [])
                    return stories[0].get("Story", {}) if stories else None
                return None
        except Exception as e:
            logger.warning(f"TAPD get_story failed: {e}")
            return None

    async def get_story_attachments(self, story_id: str) -> list:
        """Fetch attachments for a TAPD story."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/stories/get_attachments",
                    params={"workspace_id": story_id},
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
                return []
        except Exception as e:
            logger.warning(f"TAPD get_attachments failed: {e}")
            return []

    async def get_story_comments(self, story_id: str) -> list:
        """Fetch comments for a TAPD story."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/comments",
                    params={"entry_id": story_id, "entry_type": "story"},
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
                return []
        except Exception as e:
            logger.warning(f"TAPD get_comments failed: {e}")
            return []

    async def search_stories(self, keyword: str = None, story_id: str = None) -> list:
        """Search TAPD stories."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {}
                if keyword:
                    params["name"] = keyword
                if story_id:
                    params["id"] = story_id
                resp = await client.get(
                    f"{self.base_url}/stories",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
                return []
        except Exception as e:
            logger.warning(f"TAPD search failed: {e}")
            return []
