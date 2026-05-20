from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.field_extraction_chunking import split_field_extraction_items


def test_overlap_adds_paragraph_lines() -> None:
    lines = [f"{i}##text##line{i}" for i in range(1, 11)]
    source = "\n".join(lines)
    item = {"字段集": "f：d", "取值来源": source}
    parts = split_field_extraction_items([item], limit=30, overlap_paragraphs=2)
    assert len(parts) >= 2
    first_lines = parts[0]["取值来源"].splitlines()
    second_lines = parts[1]["取值来源"].splitlines()
    assert len(first_lines) >= 2
    assert first_lines[-2:] == second_lines[:2]


def test_under_limit_unchanged() -> None:
    item = {"字段集": "a：b", "取值来源": "1##text##short"}
    out = split_field_extraction_items([item], limit=10000)
    assert out == [item]
