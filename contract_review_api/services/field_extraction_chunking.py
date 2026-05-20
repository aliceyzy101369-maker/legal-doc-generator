from __future__ import annotations

import os
import re
from typing import Any

_H1_RE = re.compile(r"^#\s")
_LINE_RE = re.compile(r"^(\d+)##([^#]*?)##(.*)$")


def _chunk_limit() -> int:
    raw = os.getenv("FIELD_EXTRACTION_CHUNK_LIMIT", "15000") or "15000"
    try:
        return max(500, int(raw))
    except ValueError:
        return 15000


def _overlap_paragraphs() -> int:
    raw = os.getenv("FIELD_EXTRACTION_CHUNK_OVERLAP_PARAGRAPHS", "0") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _is_paragraph_line(line: str) -> bool:
    return bool(_LINE_RE.match(line.strip()))


def _split_source_h1_blocks(source: str) -> list[list[str]]:
    lines = str(source or "").splitlines()
    if not lines:
        return []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _H1_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        else:
            if not current:
                current = [line]
            else:
                current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _paragraph_body_lines(block_lines: list[str]) -> list[str]:
    return [ln for ln in block_lines if _is_paragraph_line(ln)]


def _apply_overlap(chunks: list[list[str]], overlap_n: int) -> list[list[str]]:
    if overlap_n <= 0 or len(chunks) <= 1:
        return chunks
    out: list[list[str]] = []
    prev_body: list[str] = []
    for idx, block in enumerate(chunks):
        lines = list(block)
        if idx > 0 and prev_body:
            prefix = prev_body[-overlap_n:]
            lines = prefix + lines
        out.append(lines)
        prev_body = _paragraph_body_lines(block)
    return out


def _pack_lines_to_chunks(lines: list[str], limit: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        extra = line if not current else "\n" + line
        if current and current_len + len(extra) > limit:
            chunks.append(current)
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(extra)
    if current:
        chunks.append(current)
    return chunks


def _split_source_by_limit(source: str, limit: int, overlap_n: int) -> list[str]:
    if len(source) <= limit:
        return [source]

    h1_blocks = _split_source_h1_blocks(source)
    if not h1_blocks:
        h1_blocks = [source.splitlines()]

    line_chunks: list[list[str]] = []
    buf: list[str] = []
    buf_len = 0
    for block in h1_blocks:
        for line in block:
            extra = line if not buf else "\n" + line
            if buf and buf_len + len(extra) > limit:
                line_chunks.append(buf)
                buf = [line]
                buf_len = len(line)
            else:
                buf.append(line)
                buf_len += len(extra)
    if buf:
        line_chunks.append(buf)

    if overlap_n > 0:
        line_chunks = _apply_overlap(line_chunks, overlap_n)

    return ["\n".join(c).strip() for c in line_chunks if c]


def split_field_extraction_items(
    items: list[dict[str, Any]],
    limit: int | None = None,
    overlap_paragraphs: int | None = None,
) -> list[dict[str, Any]]:
    """
    Split {"字段集","取值来源"} task objects when combined payload exceeds limit.

    H1-split on 取值来源, then line-based packing; optional paragraph-line overlap
  (FIELD_EXTRACTION_CHUNK_OVERLAP_PARAGRAPHS).
    """
    lim = limit if limit is not None else _chunk_limit()
    overlap = overlap_paragraphs if overlap_paragraphs is not None else _overlap_paragraphs()
    if lim <= 0:
        return list(items or [])

    out: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        field_set = str(item.get("字段集", "") or "")
        source = str(item.get("取值来源", "") or "")
        total = len(field_set) + len(source)
        if total <= lim:
            out.append(dict(item))
            continue
        source_budget = max(32, lim - len(field_set))
        parts = _split_source_by_limit(source, source_budget, overlap)
        for part in parts:
            row = dict(item)
            row["取值来源"] = part
            out.append(row)
    return out
