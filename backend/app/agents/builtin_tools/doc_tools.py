"""Document tools: PRD section search, keyword search, content statistics."""

import logging
from app.agents.tools import Tool, tool_registry

logger = logging.getLogger(__name__)


async def _search_prd_section(keyword: str, prd_content: str = "", **_kwargs) -> str:
    import json
    if not prd_content:
        return '{"error": "无PRD内容可搜索"}'
    lines = prd_content.split("\n")
    matches = []
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            context = "\n".join(lines[start:end])
            matches.append({"line": i + 1, "context": context[:500]})
    if not matches:
        return f'{{"keyword": "{keyword}", "matches": [], "message": "未找到相关内容"}}'
    return json.dumps({"keyword": keyword, "count": len(matches), "matches": matches[:10]}, ensure_ascii=False)


async def _get_prd_sections(prd_content: str = "", **_kwargs) -> str:
    import json
    if not prd_content:
        return '{"error": "无PRD内容可解析"}'
    try:
        from app.services.prd_parser import parse_prd_structure
        structure = parse_prd_structure(prd_content)
        sections = []
        for s in structure.get("sections", []):
            sections.append({
                "title": s.get("title", ""),
                "level": s.get("level", 1),
                "char_range": s.get("char_range", [0, 0]),
            })
        return json.dumps({"total_sections": len(sections), "sections": sections[:20]}, ensure_ascii=False)
    except Exception as e:
        return '{"error": "解析失败: ' + str(e)[:200] + '"}'


async def _get_prd_stats(prd_content: str = "", **_kwargs) -> str:
    import json
    if not prd_content:
        return '{"error": "无PRD内容"}'
    chars = len(prd_content)
    lines = prd_content.count("\n") + 1
    words = len(prd_content)
    return json.dumps({"total_chars": chars, "total_lines": lines, "total_words_approx": words}, ensure_ascii=False)


def register_doc_tools():
    tool_registry.register(Tool(
        name="search_prd_section",
        description="在PRD文档中搜索包含指定关键词的章节，返回上下文",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词，如'支付'、'状态'、'接口'"},
                "prd_content": {"type": "string", "description": "PRD全文内容（由系统自动填充）"},
            },
            "required": ["keyword"],
        },
        handler=_search_prd_section,
        category="document",
    ))

    tool_registry.register(Tool(
        name="get_prd_sections",
        description="获取PRD文档的章节结构列表",
        parameters={
            "type": "object",
            "properties": {
                "prd_content": {"type": "string", "description": "PRD全文内容（由系统自动填充）"},
            },
            "required": [],
        },
        handler=_get_prd_sections,
        category="document",
    ))

    tool_registry.register(Tool(
        name="get_prd_stats",
        description="获取PRD文档的统计信息：总字符数、行数等",
        parameters={
            "type": "object",
            "properties": {
                "prd_content": {"type": "string", "description": "PRD全文内容（由系统自动填充）"},
            },
            "required": [],
        },
        handler=_get_prd_stats,
        category="document",
    ))

    logger.info("Document tools registered")
