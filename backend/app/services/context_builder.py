"""Context builder — assembles review context with token budget control."""
from ..models.document import DocumentModel


class ContextBuilder:
    """Assembles context text for Agent consumption, with token budget control."""

    # Rough estimate: 1 token ≈ 3.5 chars for mixed CJK/English
    CHARS_PER_TOKEN = 3.5
    MAX_CONTEXT_CHARS = 120_000  # ~34k tokens, within DeepSeek 64k window

    @staticmethod
    def build_context(document: DocumentModel) -> str:
        """Build the full context text for LLM consumption."""
        text = document.to_context_text()
        if len(text) <= ContextBuilder.MAX_CONTEXT_CHARS:
            return text

        # Truncation strategy: keep title + TOC + first 20% + last 10%
        sections = document.sections
        toc = "\n".join(
            f"{'  ' * (s.level - 1)}§{s.ref} {s.heading}"
            for s in sections
        )

        head_budget = int(ContextBuilder.MAX_CONTEXT_CHARS * 0.55)
        tail_budget = int(ContextBuilder.MAX_CONTEXT_CHARS * 0.15)
        reserved = 2000  # for TOC + truncation notice

        head = text[:head_budget]
        tail = text[-tail_budget:]

        return (
            f"# {document.title}\n\n"
            f"[目录]\n{toc}\n\n"
            f"[注: 文档过长，已截断。保留目录、前 {head_budget} 字符与后 {tail_budget} 字符]\n\n"
            f"--- 文档前半部分 ---\n{head}\n\n"
            f"--- 文档后半部分 ---\n{tail}\n"
        )
