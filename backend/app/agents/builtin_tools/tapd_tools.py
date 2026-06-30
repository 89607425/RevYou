"""TAPD tools: query stories, attachments, comments, bugs for review context."""

import json
import logging
from app.agents.tools import Tool, tool_registry

logger = logging.getLogger(__name__)


async def _query_tapd_story(story_id: str, api_token: str = "", tapd_workspace_id: str = "", workspace_id: str = "", **kwargs) -> str:
    try:
        from app.services.tapd_service import TapdService
        ws = workspace_id or tapd_workspace_id
        tapd = TapdService(api_token=api_token, workspace_id=ws)
        story = await tapd.get_story(story_id)
        if not story:
            return json.dumps({"error": "未找到该需求"}, ensure_ascii=False)
        return json.dumps({
            "id": str(story.get("id", "")),
            "name": str(story.get("name", "")),
            "status": str(story.get("status", "")),
            "priority": str(story.get("priority", "")),
            "owner": str(story.get("owner", "")),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": "查询失败: " + str(e)[:200]}, ensure_ascii=False)


async def _query_tapd_comments(story_id: str, api_token: str = "", tapd_workspace_id: str = "", workspace_id: str = "", **kwargs) -> str:
    try:
        from app.services.tapd_service import TapdService
        ws = workspace_id or tapd_workspace_id
        tapd = TapdService(api_token=api_token, workspace_id=ws)
        comments = await tapd.get_story_comments(story_id)
        if isinstance(comments, list):
            return json.dumps({
                "count": len(comments),
                "comments": [{"author": c.get("author", ""), "content": c.get("description", "")[:200]} for c in comments[:10]]
            }, ensure_ascii=False)
        return json.dumps({"error": "查询失败"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": "查询失败: " + str(e)[:200]}, ensure_ascii=False)


async def _query_tapd_bugs(story_id: str, api_token: str = "", tapd_workspace_id: str = "", tapd_bug_workspace_id: str = "", workspace_id: str = "", **kwargs) -> str:
    try:
        from app.services.tapd_service import TapdService
        ws = workspace_id or tapd_workspace_id
        tapd = TapdService(api_token=api_token, workspace_id=ws, bug_workspace_id=tapd_bug_workspace_id)
        bugs = await tapd.get_bugs(story_id=story_id)
        if isinstance(bugs, list):
            bug_list = [{"id": b.get("id", ""), "title": b.get("title", ""), "status": b.get("status", ""), "severity": b.get("severity", "")} for b in bugs[:10]]
            return json.dumps({"count": len(bugs), "bugs": bug_list}, ensure_ascii=False)
        return json.dumps({"error": "查询失败"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": "查询失败: " + str(e)[:200]}, ensure_ascii=False)


async def _query_tapd_attachments(story_id: str, api_token: str = "", tapd_workspace_id: str = "", workspace_id: str = "", **kwargs) -> str:
    try:
        from app.services.tapd_service import TapdService
        ws = workspace_id or tapd_workspace_id
        tapd = TapdService(api_token=api_token, workspace_id=ws)
        attachments = await tapd.get_story_attachments(story_id)
        if isinstance(attachments, list):
            att_list = [{"filename": a.get("filename", ""), "type": a.get("type", ""), "description": a.get("description", "")} for a in attachments[:10]]
            return json.dumps({"count": len(attachments), "attachments": att_list}, ensure_ascii=False)
        return json.dumps({"error": "查询失败"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": "查询失败: " + str(e)[:200]}, ensure_ascii=False)


def register_tapd_tools():
    tool_registry.register(Tool(
        name="query_tapd_story",
        description="查询TAPD需求详情：获取需求的标题、状态、优先级、处理人等信息",
        parameters={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "TAPD需求ID"},
                "workspace_id": {"type": "string", "description": "TAPD项目ID（可选）"},
            },
            "required": ["story_id"],
        },
        handler=_query_tapd_story,
        category="tapd",
    ))

    tool_registry.register(Tool(
        name="query_tapd_comments",
        description="查询TAPD需求的评论历史，用于了解需求讨论背景",
        parameters={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "TAPD需求ID"},
                "workspace_id": {"type": "string", "description": "TAPD项目ID（可选）"},
            },
            "required": ["story_id"],
        },
        handler=_query_tapd_comments,
        category="tapd",
    ))

    tool_registry.register(Tool(
        name="query_tapd_bugs",
        description="查询TAPD需求关联的缺陷列表，了解已知问题和历史bug",
        parameters={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "TAPD需求ID"},
                "workspace_id": {"type": "string", "description": "TAPD项目ID（可选）"},
            },
            "required": ["story_id"],
        },
        handler=_query_tapd_bugs,
        category="tapd_bug",
    ))

    tool_registry.register(Tool(
        name="query_tapd_attachments",
        description="查询TAPD需求的附件列表，检查是否有流程图、原型图等补充材料",
        parameters={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "TAPD需求ID"},
                "workspace_id": {"type": "string", "description": "TAPD项目ID（可选）"},
            },
            "required": ["story_id"],
        },
        handler=_query_tapd_attachments,
        category="tapd",
    ))

    logger.info("TAPD tools registered")
