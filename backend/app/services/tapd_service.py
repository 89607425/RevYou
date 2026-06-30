"""TAPD read-only integration service with Bearer Token auth and dual workspace support.

Stories/tasks/iterations/wikis → story_workspace_id (产品)
Bugs → bug_workspace_id (开发和测试)
"""

import logging
from typing import Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class TapdService:
    """Service for TAPD read-only API integration.

    Uses Bearer Token authentication. Supports separate workspace IDs
    for stories (product) and bugs (dev/test).
    """

    def __init__(self, api_token: str = None, workspace_id: str = None, bug_workspace_id: str = None):
        self.api_token = api_token or settings.TAPD_DEFAULT_TOKEN
        self.workspace_id = workspace_id or settings.TAPD_DEFAULT_STORY_WORKSPACE
        self.bug_workspace_id = bug_workspace_id or settings.TAPD_DEFAULT_BUG_WORKSPACE
        self.base_url = settings.TAPD_API_BASE

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _ws_param(self) -> dict:
        return {"workspace_id": self.workspace_id} if self.workspace_id else {}

    def _bug_ws_param(self) -> dict:
        return {"workspace_id": self.bug_workspace_id} if self.bug_workspace_id else {}

    async def validate_token(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if self.workspace_id:
                    params = {"workspace_id": self.workspace_id}
                else:
                    params = self._ws_param()
                resp = await client.get(
                    f"{self.base_url}/workspaces/users",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    workspaces = []
                    for item in items:
                        ws = item.get("Workspace", {})
                        workspaces.append({
                            "id": ws.get("id", ""),
                            "name": ws.get("name", ""),
                            "status": ws.get("status", ""),
                        })
                    return {"valid": True, "message": "Token valid", "workspaces": workspaces}

                resp2 = await client.get(
                    f"{self.base_url}/stories",
                    params={"limit": 1, **self._ws_param()},
                    headers=self._headers(),
                )
                if resp2.status_code == 200:
                    return {"valid": True, "message": "Token valid"}

                return {"valid": False, "message": f"API returned {resp.status_code}/{resp2.status_code}"}
        except Exception as e:
            return {"valid": False, "message": str(e)}

    async def get_story(self, story_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"id": story_id}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/stories",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    stories = data.get("data", [])
                    story = stories[0].get("Story", {}) if stories else None
                    if story:
                        story["_workspace_id"] = self.workspace_id
                    return story
                logger.warning(f"TAPD get_story returned {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            logger.warning(f"TAPD get_story failed: {e}")
            return None

    async def get_stories_by_workspace(self, limit: int = 50) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"limit": limit}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/stories",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Story", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_stories failed: {e}")
            return []

    async def get_iterations(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"limit": 100}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/iterations",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Iteration", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_iterations failed: {e}")
            return []

    async def get_story_iteration(self, iteration_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"id": iteration_id}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/iterations",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    return items[0].get("Iteration", {}) if items else None
                return None
        except Exception as e:
            logger.warning(f"TAPD get_iteration failed: {e}")
            return None

    async def get_bugs(self, story_id: str = None, limit: int = 100) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"limit": limit}
                params.update(self._bug_ws_param())
                if story_id:
                    params["story_id"] = story_id
                resp = await client.get(
                    f"{self.base_url}/bugs",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Bug", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_bugs failed: {e}")
            return []

    async def get_tasks(self, story_id: str = None, limit: int = 100) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"limit": limit}
                params.update(self._ws_param())
                if story_id:
                    params["story_id"] = story_id
                resp = await client.get(
                    f"{self.base_url}/tasks",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Task", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_tasks failed: {e}")
            return []

    async def get_wikis(self, limit: int = 50) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"limit": limit}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/wikis",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Wiki", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_wikis failed: {e}")
            return []

    async def get_story_attachments(self, story_id: str) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"entry_id": story_id, "entry_type": "story"}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/attachments",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Attachment", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_attachments failed: {e}")
            return []

    async def get_story_comments(self, story_id: str) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"entry_id": story_id, "entry_type": "story"}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/comments",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Comment", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_comments failed: {e}")
            return []

    async def get_story_changes(self, story_id: str, limit: int = 30) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"entry_id": story_id, "entry_type": "story", "limit": limit}
                params.update(self._ws_param())
                resp = await client.get(
                    f"{self.base_url}/changes",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("Change", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD get_changes failed: {e}")
            return []

    async def compose_full_prd(self, story_id: str) -> dict:
        story = await self.get_story(story_id)
        if not story:
            logger.warning(f"Story {story_id} not found")
            return {"error": f"需求 {story_id} 未找到", "prd_text": "", "story": None}

        iteration_name = ""
        if story.get("iteration_id"):
            iteration = await self.get_story_iteration(story.get("iteration_id"))
            if iteration:
                iteration_name = iteration.get("name", "")

        bugs = await self.get_bugs(story_id)
        tasks = await self.get_tasks(story_id)
        comments = await self.get_story_comments(story_id)
        attachments = await self.get_story_attachments(story_id)
        changes = await self.get_story_changes(story_id)
        iterations = await self.get_iterations()
        wikis = await self.get_wikis()

        story_name = story.get("name", "")
        story_description = story.get("description", "")
        story_status = story.get("status", "")
        story_priority = story.get("priority", "")
        story_owner = story.get("owner", "")
        story_developer = story.get("developer", "")
        story_category = story.get("category_name", "")

        sections = []

        sections.append(f"# {story_name}\n")
        sections.append(f"**需求 ID**：{story_id}")
        sections.append(f"**状态**：{story_status} | **优先级**：{story_priority}")
        sections.append(f"**处理人**：{story_owner} | **开发人员**：{story_developer}")
        sections.append(f"**分类**：{story_category}")
        if iteration_name:
            sections.append(f"**所属迭代**：{iteration_name}")
        sections.append("")

        sections.append("## 需求描述\n")
        if story_description:
            sections.append(story_description)
        else:
            sections.append("（无详细描述）")
        sections.append("")

        fields_to_render = [
            ("acceptance_criteria", "## 验收标准"),
            ("user_story", "## 用户故事"),
            ("test_focus", "## 测试要点"),
            ("risk", "## 风险点"),
        ]
        for field, label in fields_to_render:
            val = story.get(field, "")
            if val:
                sections.append(f"{label}\n\n{val}\n")

        if tasks:
            sections.append(f"## 关联任务（{len(tasks)} 个）\n")
            for i, t in enumerate(tasks, 1):
                sections.append(f"### 任务 {i}：{t.get('name', '无标题')}")
                sections.append(f"- 状态：{t.get('status', '')} | 负责人：{t.get('owner', '')}")
                if t.get("description"):
                    sections.append(f"- 描述：{t.get('description', '')}")
                sections.append("")

        if bugs:
            sections.append(f"## 关联缺陷（{len(bugs)} 个，来源：Bug 工作区）\n")
            for i, b in enumerate(bugs, 1):
                sections.append(f"### Bug {i}：{b.get('title', '无标题')}")
                sections.append(f"- 严重程度：{b.get('severity', '')} | 状态：{b.get('status', '')}")
                sections.append(f"- 负责人：{b.get('current_owner', '')}")
                if b.get("description"):
                    sections.append(f"- 描述：{b.get('description', '')[:500]}")
                sections.append("")

        if iterations:
            sections.append(f"## 项目迭代（{len(iterations)} 个）\n")
            for it in iterations[:10]:
                sections.append(f"- **{it.get('name', '')}**：{it.get('startdate', '')} ~ {it.get('enddate', '')} ({it.get('status', '')})")
            sections.append("")

        if wikis:
            sections.append(f"## 项目 Wiki（{len(wikis)} 篇）\n")
            for w in wikis[:10]:
                sections.append(f"- **{w.get('title', '无标题')}**（{w.get('modifier', '')} 修改于 {w.get('modified', '')}）")
                if w.get("description"):
                    sections.append(f"  {w.get('description', '')[:300]}")
            sections.append("")

        if comments:
            sections.append(f"## 需求评论（{len(comments)} 条）\n")
            for c in comments[:20]:
                author = c.get("author", "未知")
                created = c.get("created", "")
                content = c.get("description", "")
                sections.append(f"**{author}** ({created})：{content}")
                sections.append("")

        if changes:
            sections.append(f"## 变更历史（最近 {len(changes)} 条）\n")
            for ch in changes[:15]:
                sections.append(f"- {ch.get('created', '')} | {ch.get('author', '')}：{ch.get('field', '')} 从「{ch.get('value_before', '')}」→「{ch.get('value_after', '')}」")
            sections.append("")

        if attachments:
            sections.append(f"## 附件（{len(attachments)} 个）\n")
            for a in attachments:
                sections.append(f"- {a.get('filename', '')}（{a.get('content_type', '')}，{a.get('owner', '')} 上传于 {a.get('created', '')}）")
            sections.append("")

        prd_text = "\n".join(sections)

        return {
            "prd_text": prd_text,
            "story": {
                "id": story_id,
                "name": story_name,
                "status": story_status,
                "priority": story_priority,
                "owner": story_owner,
                "iteration_name": iteration_name,
            },
            "stats": {
                "tasks": len(tasks),
                "bugs": len(bugs),
                "comments": len(comments),
                "attachments": len(attachments),
                "iterations": len(iterations),
                "wikis": len(wikis),
                "changes": len(changes),
            },
        }

    async def search_stories(self, keyword: str = None, story_id: str = None) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {}
                params.update(self._ws_param())
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
                    return [item.get("Story", {}) for item in data.get("data", [])]
                return []
        except Exception as e:
            logger.warning(f"TAPD search failed: {e}")
            return []
