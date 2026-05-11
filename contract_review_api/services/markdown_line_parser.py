from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

from contract_review_api.core.models import Paragraph

# Dify-style line: pid##category##body  (category may be Chinese/ASCII)
_LINE_RE = re.compile(r"^(\d+)##([^#]*?)##(.*)$")

# Dify A/B branches use "number" vs historical typo "nuber"; treat both as the same bucket.
_NUMBERISH_CATEGORIES = frozenset({"number", "nuber"})


def _configured_extra_paragraph_categories() -> frozenset[str]:
    raw = os.getenv("MARKDOWN_PARAGRAPH_CATEGORY_ALLOWLIST", "") or ""
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def is_numberish_line_category(category: str) -> bool:
    return str(category or "").lower().strip() in _NUMBERISH_CATEGORIES


def is_paragraph_eligible_category(category: str) -> bool:
    """
    Paragraph extraction uses Dify-style filtering: default only number/nuber.
    Optional comma-separated MARKDOWN_PARAGRAPH_CATEGORY_ALLOWLIST extends this (case-insensitive category names).
    """
    if is_numberish_line_category(category):
        return True
    cat = str(category or "").strip().lower()
    return bool(cat) and cat in _configured_extra_paragraph_categories()


@dataclass(frozen=True)
class MarkdownLineRecord:
    pid: int
    category: str
    text: str
    field_key: str
    raw: str


def parse_markdown_lines(text: str) -> list[MarkdownLineRecord]:
    """Parse well-formed ``pid##category##text`` lines; skip invalid lines."""
    out: list[MarkdownLineRecord] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        pid = int(m.group(1))
        category = str(m.group(2) or "").strip()
        body = str(m.group(3) or "").strip()
        field_key = category or "unknown"
        out.append(MarkdownLineRecord(pid=pid, category=category, text=body, field_key=field_key, raw=raw_line.rstrip()))
    return _merge_duplicate_pids(out)


def _merge_duplicate_pids(records: Iterable[MarkdownLineRecord]) -> list[MarkdownLineRecord]:
    buckets: dict[int, list[MarkdownLineRecord]] = {}
    order: list[int] = []
    for r in records:
        if r.pid not in buckets:
            order.append(r.pid)
        buckets.setdefault(r.pid, []).append(r)
    merged: list[MarkdownLineRecord] = []
    for pid in order:
        items = buckets[pid]
        if len(items) == 1:
            merged.append(items[0])
            continue
        cat = items[0].category
        fk = items[0].field_key
        body = "\n".join(x.text for x in items if x.text)
        raw = "\n".join(x.raw for x in items)
        merged.append(MarkdownLineRecord(pid=pid, category=cat, text=body, field_key=fk, raw=raw))
    return merged


def is_dify_markdown_line_document(text: str) -> bool:
    """Heuristic: enough lines look like pid##cat##text."""
    nonempty = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if len(nonempty) < 2:
        return False
    hits = sum(1 for ln in nonempty if _LINE_RE.match(ln))
    return hits >= 2 and hits / len(nonempty) >= 0.25


def paragraphs_from_markdown_lines(review_id: str, text: str) -> list[Paragraph]:
    """Build Paragraph objects using pid as paragraph_no and body as extraction text."""
    records = parse_markdown_lines(text)
    filtered = [r for r in records if is_paragraph_eligible_category(r.category)]
    return [
        Paragraph(
            review_id=review_id,
            doc_type="dify_markdown_line",
            paragraph_no=r.pid,
            text=r.text,
        )
        for r in filtered
    ]
