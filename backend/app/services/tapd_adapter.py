"""TAPD adapter — direct httpx calls to api.tapd.cn."""
import base64
import logging
import re
from typing import Optional
import httpx
from ..config import settings
from ..models.document import DocumentModel, Section, SourceType, TapdContext

logger = logging.getLogger(__name__)

STORY_FIELDS = ("id,name,description,status,owner,priority_label,"
                "iteration_id,category_id,created")


def html_to_text(html: str) -> str:
    """Convert TAPD rich-text (HTML) description to readable markdown-ish text."""
    if not html or "<" not in html:
        return html or ""

    try:
        from lxml import html as lxml_html
        root = lxml_html.fromstring(f"<div>{html}</div>")
    except Exception:
        # Fallback: crude tag stripping
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text)
        return re.sub(r"<[^>]+>", "", text).strip()

    # Remove style/script
    for bad in root.xpath("//style|//script"):
        bad.getparent().remove(bad)

    lines: list[str] = []

    def walk(node):
        tag = node.tag if isinstance(node.tag, str) else ""
        if tag in ("p", "div"):
            emit_text(node)
            lines.append("")
        elif tag == "br":
            lines.append("")
        elif tag == "li":
            lines.append("- " + (node.text_content() or "").strip())
        elif tag in ("h1", "h2", "h3", "h4"):
            lines.append("")
            lines.append("# " * (int(tag[1]) - 1) + (node.text_content() or "").strip())
            lines.append("")
        elif tag == "tr":
            cells = [(td.text_content() or "").strip()
                     for td in node.xpath("./td|./th")]
            lines.append("| " + " | ".join(cells) + " |")
        else:
            emit_text(node)

    def emit_text(node):
        text = node.text_content()
        if text and text.strip():
            lines.append(text.strip())

    walk(root)
    # Collapse multiple blank lines
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


class TAPDAdapter:
    def __init__(self):
        self.base_url = settings.tapd_api_url
        # TAPD uses Basic Auth: api_user:api_password base64 encoded
        token = settings.tapd_token
        if token and ":" in token:
            encoded = base64.b64encode(token.encode()).decode()
            self.auth_header = f"Basic {encoded}"
        elif token:
            self.auth_header = f"Bearer {token}"
        else:
            self.auth_header = ""

    async def get_story(self, workspace_id: str, story_id: str) -> dict:
        """Fetch a story/requirement by ID.

        Prefers the list endpoint filtered by id (works with personal tokens
        that have stories::list but not stories::get permission).
        """
        headers = {"Authorization": self.auth_header} if self.auth_header else {}
        fields = STORY_FIELDS

        # Strategy 1: list endpoint with id filter
        url = f"{self.base_url}/stories"
        params = {"workspace_id": workspace_id, "id": story_id, "fields": fields}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == 1:
                items = data.get("data", [])
                if isinstance(items, list) and items:
                    return items[0].get("Story", {})

        # Strategy 2: dedicated get endpoint (needs stories::get permission)
        url = f"{self.base_url}/stories/get"
        params = {"workspace_id": workspace_id, "id": story_id, "fields": fields}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            stories = data.get("data", {}).get("Story", {})
            return stories if stories else {}

    async def get_comments(self, workspace_id: str, entry_id: str) -> list[dict]:
        """Fetch comments for a story."""
        url = f"{self.base_url}/comments"
        params = {
            "workspace_id": workspace_id,
            "entry_id": entry_id,
            "entry_type": "stories",
        }
        headers = {"Authorization": self.auth_header} if self.auth_header else {}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                comments = data.get("data", [])
                return comments if comments else []
        except Exception as e:
            logger.warning(f"TAPD get_comments failed: {e}")
            return []

    async def get_related_bugs(self, workspace_id: str, story_id: str) -> list[dict]:
        """Fetch related bugs for a story."""
        url = f"{self.base_url}/relations/get_dev_relation"
        params = {
            "workspace_id": workspace_id,
            "object_type": "story",
            "object_id": story_id,
        }
        headers = {"Authorization": self.auth_header} if self.auth_header else {}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"TAPD get_related_bugs failed: {e}")
            return []

    async def get_related_test_cases(self, workspace_id: str,
                                      story_id: str) -> list[dict]:
        """Fetch related test cases for a story."""
        url = f"{self.base_url}/relations/get_test_relation"
        params = {
            "workspace_id": workspace_id,
            "object_type": "story",
            "object_id": story_id,
        }
        headers = {"Authorization": self.auth_header} if self.auth_header else {}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"TAPD get_related_test_cases failed: {e}")
            return []

    async def fetch_document(self, workspace_id: str, story_id: str) -> DocumentModel:
        """Fetch a TAPD story and convert to DocumentModel."""
        story = await self.get_story(workspace_id, story_id)
        if not story:
            raise ValueError(f"TAPD story {story_id} not found in workspace {workspace_id}")

        # TAPD descriptions are rich-text HTML — convert to markdown-ish text
        raw_description = story.get("description", "") or ""
        description = html_to_text(raw_description)

        # Build sections: convert to markdown text then reuse markdown logic
        # (DocParser handles heading detection and section refs)
        from .doc_parser import DocParser
        md_text = f"# {story.get('name', f'TAPD Story {story_id}')}\n\n{description}"
        base_doc = DocParser.parse_markdown(md_text)
        sections = base_doc.sections

        # Fallback: if no headings found, treat paragraphs as sections
        if not sections and description:
            sections = [Section(ref="1", heading="(需求描述)", level=1,
                                paragraphs=description.split("\n"))]

        # Enrich with context
        tapd_ctx = TapdContext(
            story_id=story_id,
            status=story.get("status", ""),
            owner=story.get("owner", ""),
            priority=story.get("priority_label", ""),
            iteration_id=story.get("iteration_id", ""),
            category_id=story.get("category_id", ""),
        )

        # Try enrichment (non-blocking, won't fail if unavailable)
        if settings.tapd_token:
            comments = await self.get_comments(workspace_id, story_id)
            tapd_ctx.comments = comments
            bugs = await self.get_related_bugs(workspace_id, story_id)
            tapd_ctx.related_bugs = bugs
            tcases = await self.get_related_test_cases(workspace_id, story_id)
            tapd_ctx.related_test_cases = tcases

        return DocumentModel(
            source_type=SourceType.tapd,
            title=story.get("name", f"TAPD Story {story_id}"),
            raw_markdown=description,
            sections=sections,
            metadata={
                "workspace_id": workspace_id,
                "story_id": story_id,
                "status": story.get("status"),
                "owner": story.get("owner"),
            },
            tapd_context=tapd_ctx,
        )

    async def search_stories(self, workspace_id: str, keyword: str = "",
                              limit: int = 20) -> list[dict]:
        """Search stories by keyword in a workspace."""
        url = f"{self.base_url}/stories"
        params = {
            "workspace_id": workspace_id,
            "limit": str(limit),
        }
        if keyword:
            params["name"] = keyword
        headers = {"Authorization": self.auth_header} if self.auth_header else {}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            stories = data.get("data", [])
            return stories if stories else []


tapd_adapter = TAPDAdapter()
