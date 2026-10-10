from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

from .extractor import ExtractedPage


HEADING_RE = re.compile(
    r"^#{1,6}\s+|^(?:PHẦN|CHƯƠNG|MỤC|TIỂU MỤC)\s+[IVXLCDM\d]+\b|^Điều\s+\d+[a-zA-Z]?(?:[–−-]\d+)?\s*[.:—–-]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LegalChunk:
    chunk_index: int
    page_from: int
    page_to: int
    heading: str | None
    content: str
    content_sha256: str


@dataclass(frozen=True)
class _Unit:
    page: int
    heading: str | None
    text: str


def _units(pages: Iterable[ExtractedPage]) -> list[_Unit]:
    result: list[_Unit] = []
    current_heading: str | None = None
    clause: str | None = None
    point: str | None = None
    clause_intro = ""
    end_matter = False
    for page in pages:
        paragraphs = [part.strip() for part in re.split(
            r"\n\s*\n|(?<=\.)\s*\n|\n(?=\s*(?:Điều\s+\d+\s*[.:]|\d+\.\s|[a-zđ]\)\s))",
            page.text) if part.strip()]
        for paragraph in paragraphs:
            first_line = paragraph.splitlines()[0].strip()
            if re.search(r"^(?:\d{1,3}\s+)?Phụ lục\b", first_line, re.I):
                current_heading, clause, point, clause_intro, end_matter = "Phụ lục", None, None, "", False
            elif re.search(r"Nơi\s+nhận\s*:", first_line, re.I):
                current_heading, clause, point, clause_intro, end_matter = None, None, None, "", True
            if end_matter:
                continue
            paragraph = re.sub(r"^[|_‘'\s]+(?=\d+\.\s|[a-zđ]\)\s)", "", paragraph)
            if re.fullmatch(r"\d{1,3}", paragraph):
                continue  # printed page number, not a legal provision
            if HEADING_RE.search(first_line):
                current_heading = first_line[:300]
                clause = None
                point, clause_intro = None, ""
            elif current_heading and re.match(r"^\d+\.\s", paragraph):
                clause = "Khoản " + paragraph.split(".", 1)[0]
                point, clause_intro = None, re.sub(r"\s+", " ", paragraph)
            elif clause and re.match(r"^[a-zđ]\)\s", paragraph):
                point = "Điểm " + paragraph[0]
                paragraph = clause_intro + "\n\n" + paragraph
            heading = current_heading
            if clause:
                heading = f"{current_heading} | {clause}"
            if point:
                heading = f"{heading} | {point}"
            result.append(_Unit(page.number, heading, re.sub(r"\s+", " ", paragraph)))
    return result


def chunk_pages(
    pages: Iterable[ExtractedPage],
    *,
    target_chars: int = 1600,
    overlap_chars: int = 220,
    min_chars: int = 120,
) -> list[LegalChunk]:
    """Chunk legal text while retaining article/chapter headings and page ranges."""
    if target_chars < 400 or overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError("Kích thước chunk/overlap không hợp lệ")
    units = _units(pages)
    chunks: list[LegalChunk] = []
    buffer: list[_Unit] = []
    size = 0

    def flush(*, retain_overlap: bool = True) -> None:
        nonlocal buffer, size
        if not buffer:
            return
        content = "\n\n".join(unit.text for unit in buffer).strip()
        # Short clauses and the final tail still contain enforceable rules.
        if content:
            chunks.append(
                LegalChunk(
                    chunk_index=len(chunks),
                    page_from=min(unit.page for unit in buffer),
                    page_to=max(unit.page for unit in buffer),
                    heading=next((unit.heading for unit in reversed(buffer) if unit.heading), None),
                    content=content,
                    content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )
        overlap: list[_Unit] = []
        overlap_size = 0
        for unit in reversed(buffer) if retain_overlap else []:
            remaining = overlap_chars - overlap_size
            if remaining <= 0:
                break
            tail = unit.text[-remaining:]
            overlap.insert(0, _Unit(unit.page, unit.heading, tail))
            overlap_size += len(tail)
        buffer = overlap
        size = overlap_size

    for unit in units:
        if buffer and buffer[-1].heading != unit.heading:
            flush(retain_overlap=False)
        # Split pathological OCR paragraphs without dropping any text.
        parts = []
        remaining = unit.text
        while len(remaining) > target_chars:
            boundary = remaining.rfind(" ", 0, target_chars)
            boundary = boundary if boundary > target_chars // 2 else target_chars
            parts.append(remaining[:boundary])
            remaining = remaining[boundary:].lstrip()
        if remaining:
            parts.append(remaining)
        for part in parts:
            part_unit = _Unit(unit.page, unit.heading, part)
            if buffer and size + len(part) + 2 > target_chars:
                flush()
            buffer.append(part_unit)
            size += len(part) + 2
    flush()
    return chunks
