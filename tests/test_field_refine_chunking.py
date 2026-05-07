"""Unit tests for LLM field extraction chunking helpers (no real HTTP)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services import llm_engine


def test_chunk_text_splits_by_size() -> None:
    s = "abcdefghij"
    parts = llm_engine._chunk_text_for_field_refine(s, 3, 10)
    assert parts == ["abc", "def", "ghi", "j"]


def test_chunk_text_respects_max_chunks() -> None:
    s = "x" * 10
    parts = llm_engine._chunk_text_for_field_refine(s, 2, 3)
    assert parts == ["xx", "xx", "xx"]
    assert len("".join(parts)) == 6


def test_merge_llm_field_map_parts_concat_values() -> None:
    a = {"k": {"value": "A", "evidence_paragraphs": [1], "confidence": 0.8}}
    b = {"k": {"value": "B", "evidence_paragraphs": [2], "confidence": 0.9}}
    m = llm_engine._merge_llm_field_map_parts(a, b)
    assert m["k"]["value"] == "A\nB"
    assert m["k"]["evidence_paragraphs"] == [1, 2]


def test_merge_llm_field_map_parts_dedup_identical_value() -> None:
    a = {"k": {"value": "Same", "evidence_paragraphs": [1], "confidence": 0.8}}
    b = {"k": {"value": "Same", "evidence_paragraphs": [3], "confidence": 0.7}}
    m = llm_engine._merge_llm_field_map_parts(a, b)
    assert m["k"]["value"] == "Same"
    assert set(m["k"]["evidence_paragraphs"]) == {1, 3}


def test_merge_skips_empty_right_value() -> None:
    a = {"k": {"value": "X", "evidence_paragraphs": [], "confidence": 0.5}}
    b = {"k": {"value": "", "evidence_paragraphs": [9], "confidence": 0.99}}
    m = llm_engine._merge_llm_field_map_parts(a, b)
    assert m["k"]["value"] == "X"
