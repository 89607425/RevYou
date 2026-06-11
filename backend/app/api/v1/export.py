"""Export endpoints: review reports (Markdown/PDF) and issue lists (Excel/CSV)."""
import io
import csv
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.review import ReviewSession, ReviewIssue

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])


def _build_markdown_report(session: ReviewSession, issues: list[ReviewIssue]) -> str:
    """Build a Markdown review report."""
    lines = [
        f"# AI需求审查报告",
        f"",
        f"**审查会话**：{session.session_id}",
        f"**审查模式**：{'自主Agent模式' if session.agent_mode == 'AUTONOMOUS' else '确定性工作流'}",
        f"**需求来源**：{session.prd_source}",
        f"**创建时间**：{session.created_at.isoformat() if session.created_at else '-'}",
        f"**完成时间**：{session.completed_at.isoformat() if session.completed_at else '-'}",
        f"",
        f"---",
        f"",
        f"## 问题概览",
        f"",
    ]

    high_count = sum(1 for i in issues if i.severity == "HIGH")
    med_count = sum(1 for i in issues if i.severity == "MEDIUM")
    low_count = sum(1 for i in issues if i.severity == "LOW")

    lines.extend([
        f"- 总问题数：**{len(issues)}**",
        f"- 高严重等级：**{high_count}**",
        f"- 中严重等级：**{med_count}**",
        f"- 低严重等级：**{low_count}**",
        f"",
        f"---",
        f"",
        f"## 按Agent分组",
        f"",
    ])

    for agent in ("PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"):
        agent_issues = [i for i in issues if i.source_agent == agent]
        agent_labels = {"PM_REVIEW": "产品视角 (PM)", "DEV_REVIEW": "技术视角 (Dev)", "QA_REVIEW": "测试视角 (QA)"}
        lines.append(f"### {agent_labels[agent]} ({len(agent_issues)} 个问题)")
        lines.append("")
        for idx, issue in enumerate(agent_issues, 1):
            severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(issue.severity, "")
            lines.extend([
                f"#### {idx}. {severity_emoji} [{issue.severity}] {issue.title}",
                f"",
                f"**问题类型**：{issue.issue_type} | **置信度**：{issue.confidence}",
                f"",
                f"**描述**：{issue.description}",
                f"",
            ])
            if issue.suggestion:
                lines.append(f"**建议**：{issue.suggestion}")
                lines.append("")
            if issue.prd_section:
                lines.append(f"**关联章节**：{issue.prd_section}")
                lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


@router.get("/sessions/{session_id}/export/report")
async def export_report(
    session_id: str,
    format: str = Query(default="markdown"),
    include_low_confidence: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ReviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    query = select(ReviewIssue).where(ReviewIssue.session_id == session_id)
    if not include_low_confidence:
        query = query.where(ReviewIssue.confidence >= 0.5)

    result = await db.execute(query.order_by(ReviewIssue.severity.desc(), ReviewIssue.source_agent))
    issues = result.scalars().all()

    if format == "markdown":
        md_content = _build_markdown_report(session, issues)
        return StreamingResponse(
            io.BytesIO(md_content.encode("utf-8")),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=review_report_{session_id}.md"},
        )
    elif format == "pdf":
        # Simple text-based PDF fallback (full PDF rendering requires @react-pdf/renderer on frontend)
        md_content = _build_markdown_report(session, issues)
        return StreamingResponse(
            io.BytesIO(md_content.encode("utf-8")),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=review_report_{session_id}.pdf"},
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported format")


@router.get("/sessions/{session_id}/export/issues")
async def export_issues(
    session_id: str,
    format: str = Query(default="csv"),
    include_low_confidence: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ReviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    query = select(ReviewIssue).where(ReviewIssue.session_id == session_id)
    if not include_low_confidence:
        query = query.where(ReviewIssue.confidence >= 0.5)

    result = await db.execute(query.order_by(ReviewIssue.severity.desc(), ReviewIssue.source_agent))
    issues = result.scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["问题ID", "来源Agent", "问题类型", "严重等级", "标题", "描述", "建议", "关联章节", "置信度", "状态"])
        for issue in issues:
            writer.writerow([
                issue.issue_id, issue.source_agent, issue.issue_type, issue.severity,
                issue.title, issue.description, issue.suggestion or "",
                issue.prd_section or "", float(issue.confidence) if issue.confidence else "", issue.status,
            ])
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=issues_{session_id}.csv"},
        )
    elif format == "xlsx":
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "审查问题"
            ws.append(["问题ID", "来源Agent", "问题类型", "严重等级", "标题", "描述", "建议", "关联章节", "置信度", "状态"])
            for issue in issues:
                ws.append([
                    issue.issue_id, issue.source_agent, issue.issue_type, issue.severity,
                    issue.title, issue.description, issue.suggestion or "",
                    issue.prd_section or "", float(issue.confidence) if issue.confidence else "", issue.status,
                ])
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=issues_{session_id}.xlsx"},
            )
        except ImportError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Excel export not available")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported format")
