from __future__ import annotations

import re
from dataclasses import dataclass


PAGE_RE = re.compile(r"^#\s*Page\s+(\d+)\s*$", re.IGNORECASE)
SHEET_RE = re.compile(r"^#\s*Sheet:\s*(.+?)\s*$", re.IGNORECASE)
SLIDE_RE = re.compile(r"^#\s*Slide\s+(\d+)\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class ChunkMetadata:
    page_no: int | None = None
    sheet_name: str = ""
    slide_no: int | None = None
    heading_path: str = ""


@dataclass(frozen=True)
class StructuredChunk:
    content: str
    page_no: int | None = None
    sheet_name: str = ""
    slide_no: int | None = None
    heading_path: str = ""


def build_structured_chunks(
    content: str,
    *,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[StructuredChunk]:
    if not content.strip():
        return []

    blocks = _split_into_blocks(content)
    if not blocks:
        return []

    chunks: list[StructuredChunk] = []
    for block in blocks:
        text = block.content.strip()
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    StructuredChunk(
                        content=chunk_text,
                        page_no=block.page_no,
                        sheet_name=block.sheet_name,
                        slide_no=block.slide_no,
                        heading_path=block.heading_path,
                    )
                )
            if end == len(text):
                break
            start = max(0, end - overlap)

    return chunks


def _split_into_blocks(content: str) -> list[StructuredChunk]:
    lines = content.splitlines()
    heading_stack: list[str] = []
    metadata = ChunkMetadata()
    buffer: list[str] = []
    blocks: list[StructuredChunk] = []

    def flush_buffer() -> None:
        text = "\n".join(buffer).strip()
        if text:
            blocks.append(
                StructuredChunk(
                    content=text,
                    page_no=metadata.page_no,
                    sheet_name=metadata.sheet_name,
                    slide_no=metadata.slide_no,
                    heading_path=metadata.heading_path,
                )
            )
        buffer.clear()

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            flush_buffer()
            continue

        page_match = PAGE_RE.match(stripped)
        if page_match:
            flush_buffer()
            metadata = ChunkMetadata(
                page_no=int(page_match.group(1)),
                sheet_name=metadata.sheet_name,
                slide_no=metadata.slide_no,
                heading_path=metadata.heading_path,
            )
            continue

        sheet_match = SHEET_RE.match(stripped)
        if sheet_match:
            flush_buffer()
            metadata = ChunkMetadata(
                page_no=metadata.page_no,
                sheet_name=sheet_match.group(1).strip(),
                slide_no=metadata.slide_no,
                heading_path=metadata.heading_path,
            )
            continue

        slide_match = SLIDE_RE.match(stripped)
        if slide_match:
            flush_buffer()
            metadata = ChunkMetadata(
                page_no=metadata.page_no,
                sheet_name=metadata.sheet_name,
                slide_no=int(slide_match.group(1)),
                heading_path=metadata.heading_path,
            )
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            flush_buffer()
            level = len(heading_match.group(1))
            heading_title = heading_match.group(2).strip()
            while len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(heading_title)
            metadata = ChunkMetadata(
                page_no=metadata.page_no,
                sheet_name=metadata.sheet_name,
                slide_no=metadata.slide_no,
                heading_path=" > ".join(heading_stack),
            )
            continue

        if stripped.startswith(("- ", "* ")):
            buffer.append(stripped[2:].strip())
            continue
        buffer.append(stripped)

    flush_buffer()
    return blocks
