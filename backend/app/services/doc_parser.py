"""Document parser — Markdown / PDF → DocumentModel."""
import re
import fitz  # PyMuPDF
from pathlib import Path
from ..models.document import DocumentModel, Section, SourceType


class DocParser:
    @staticmethod
    def parse_markdown(content: str, filename: str = "") -> DocumentModel:
        """Parse markdown text into DocumentModel with sections."""
        title = filename or "Untitled Document"
        lines = content.split("\n")
        sections: list[Section] = []
        current_section: Section | None = None
        section_counter = 0

        for line in lines:
            # Match markdown headings: #, ##, ###, etc.
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                # Prefer first H1 as title over filename
                if level == 1 and not any(s.level == 1 for s in sections):
                    title = heading_text

                section_counter += 1
                ref = str(section_counter)
                current_section = Section(
                    ref=ref,
                    heading=heading_text,
                    level=level,
                    paragraphs=[]
                )
                sections.append(current_section)
            elif line.strip():
                if current_section:
                    current_section.paragraphs.append(line.strip())
                else:
                    # Content before first heading
                    section_counter += 1
                    current_section = Section(
                        ref=str(section_counter),
                        heading="(前置内容)",
                        level=1,
                        paragraphs=[line.strip()]
                    )
                    sections.append(current_section)

        return DocumentModel(
            source_type=SourceType.markdown,
            title=title,
            raw_markdown=content,
            sections=sections,
            metadata={"filename": filename}
        )

    @staticmethod
    def parse_pdf(file_path: str, filename: str = "") -> DocumentModel:
        """Parse PDF into DocumentModel using PyMuPDF."""
        title = filename or Path(file_path).stem or "Untitled Document"
        doc = fitz.open(file_path)
        all_text = ""
        sections: list[Section] = []
        section_counter = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    text_parts = []
                    max_font_size = 0
                    for span in line["spans"]:
                        text_parts.append(span["text"])
                        max_font_size = max(max_font_size, span["size"])

                    line_text = "".join(text_parts).strip()
                    if not line_text:
                        continue

                    all_text += line_text + "\n"

                    # Heuristic: larger font sizes or bold text are likely headings
                    is_heading = max_font_size >= 14 or (
                        max_font_size >= 12 and any(
                            s["flags"] & 2 ** 4  # bold flag
                            for s in line["spans"]
                        )
                    )

                    if is_heading and len(line_text) < 80:
                        section_counter += 1
                        current_section = Section(
                            ref=str(section_counter),
                            heading=line_text,
                            level=2,
                            paragraphs=[]
                        )
                        sections.append(current_section)
                    else:
                        if sections:
                            sections[-1].paragraphs.append(line_text)
                        else:
                            section_counter += 1
                            sections.append(Section(
                                ref=str(section_counter),
                                heading="(前置内容)",
                                level=1,
                                paragraphs=[line_text]
                            ))

        doc.close()

        # If no title found, try to extract from first heading
        if title == "Untitled Document" and sections:
            title = sections[0].heading

        return DocumentModel(
            source_type=SourceType.pdf,
            title=title,
            raw_markdown=all_text.strip(),
            sections=sections,
            metadata={"filename": filename, "page_count": len(doc)}
        )

    @staticmethod
    def parse(file_path: str, source_type: str = "") -> DocumentModel:
        """Auto-detect and parse based on file extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        filename = path.name

        if ext == ".md" or source_type == "markdown":
            content = path.read_text(encoding="utf-8")
            return DocParser.parse_markdown(content, filename)
        elif ext == ".pdf" or source_type == "pdf":
            return DocParser.parse_pdf(str(path), filename)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
