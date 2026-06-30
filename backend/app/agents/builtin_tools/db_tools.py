"""Database tools: query historical review issues, find similar problems."""

import json
import logging
from app.agents.tools import Tool, tool_registry

logger = logging.getLogger(__name__)


async def _query_historical_issues(
    project_id: str = "",
    issue_type: str = "",
    severity: str = "",
    limit: int = 20,
    **_kwargs,
) -> str:
    try:
        from app.core.database import async_session_factory
        from app.models.review import ReviewIssue
        from sqlalchemy import select

        async with async_session_factory() as db:
            stmt = select(ReviewIssue)
            if project_id:
                stmt = stmt.where(ReviewIssue.session.has(project_id=project_id))
            if issue_type:
                stmt = stmt.where(ReviewIssue.issue_type == issue_type)
            if severity:
                stmt = stmt.where(ReviewIssue.severity == severity)
            stmt = stmt.order_by(ReviewIssue.created_at.desc()).limit(limit)
            result = await db.execute(stmt)
            issues = result.scalars().all()

            issue_list = []
            for iss in issues:
                issue_list.append({
                    "title": iss.title,
                    "issue_type": iss.issue_type,
                    "severity": iss.severity,
                    "source_agent": iss.source_agent,
                })
            return json.dumps({"count": len(issue_list), "issues": issue_list}, ensure_ascii=False)
    except Exception as e:
        return '{"error": "查询历史问题失败: ' + str(e)[:200] + '"}'


async def _query_issue_statistics(project_id: str = "", **_kwargs) -> str:
    try:
        from app.core.database import async_session_factory
        from app.models.review import ReviewIssue
        from sqlalchemy import select, func

        async with async_session_factory() as db:
            stmt = select(
                ReviewIssue.severity,
                func.count(ReviewIssue.issue_id).label("cnt"),
            )
            if project_id:
                stmt = stmt.where(ReviewIssue.session.has(project_id=project_id))
            stmt = stmt.group_by(ReviewIssue.severity)
            result = await db.execute(stmt)
            rows = result.all()

            stats = {}
            for severity, count in rows:
                stats[severity] = count
            return json.dumps(stats, ensure_ascii=False)
    except Exception as e:
        return '{"error": "查询统计失败: ' + str(e)[:200] + '"}'


def register_db_tools():
    tool_registry.register(Tool(
        name="query_historical_issues",
        description="查询项目中历史审查发现的问题，按类型和严重等级过滤，用于了解常见问题模式",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "项目ID（可选）"},
                "issue_type": {"type": "string", "description": "问题类型：TECHNICAL_RISK/LOGIC_GAP/TEST_MISSING/DATA_INCONSISTENCY（可选）"},
                "severity": {"type": "string", "description": "严重等级：HIGH/MEDIUM/LOW（可选）"},
                "limit": {"type": "integer", "description": "返回数量，默认20"},
            },
            "required": [],
        },
        handler=_query_historical_issues,
        category="database",
    ))

    tool_registry.register(Tool(
        name="query_issue_statistics",
        description="查询项目中历史问题的统计信息：各级别问题数量分布",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "项目ID（可选）"},
            },
            "required": [],
        },
        handler=_query_issue_statistics,
        category="database",
    ))

    logger.info("Database tools registered")
