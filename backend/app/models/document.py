"""Document model — normalized representation of input requirement docs."""
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class SourceType(str, Enum):
    markdown = "markdown"
    pdf = "pdf"
    tapd = "tapd"


class Section(BaseModel):
    ref: str = Field(description="Section reference, e.g. '2.1'")
    heading: str
    level: int = Field(description="Heading level: 1, 2, 3...")
    paragraphs: list[str] = Field(default_factory=list)


class TapdContext(BaseModel):
    story_id: str = ""
    status: str = ""
    owner: str = ""
    priority: str = ""
    iteration_id: str = ""
    category_id: str = ""
    comments: list[dict] = Field(default_factory=list)
    related_bugs: list[dict] = Field(default_factory=list)
    related_test_cases: list[dict] = Field(default_factory=list)


class DocumentModel(BaseModel):
    source_type: SourceType
    title: str
    raw_markdown: str = Field(description="Normalized markdown text")
    sections: list[Section] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    tapd_context: Optional[TapdContext] = None

    def to_context_text(self) -> str:
        """Return a context-friendly text with section markers."""
        if not self.sections:
            return self.raw_markdown
        lines = [f"# {self.title}"]
        for s in self.sections:
            prefix = "#" * max(1, s.level)
            lines.append(f"\n{prefix} [{s.ref}] {s.heading}")
            for i, p in enumerate(s.paragraphs, 1):
                lines.append(p)
        return "\n".join(lines)
