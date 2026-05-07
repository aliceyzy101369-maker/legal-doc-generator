"""Unit tests for LLM field extraction chunking helpers (no real HTTP)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

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


def test_parallel_chunks_merge_in_index_order() -> None:
    """Second chunk finishes first; merged values must follow chunk 0 then chunk 1."""

    def fake_one(text: str, field_names: list[str], **kwargs: object):
        if text.startswith("a"):
            time.sleep(0.06)
            return ({"f": {"value": "chunk0", "evidence_paragraphs": [], "confidence": 0.9}}, [])
        if text.startswith("b"):
            return ({"f": {"value": "chunk1", "evidence_paragraphs": [], "confidence": 0.9}}, [])
        return ({}, [])

    merged, _warns = llm_engine._run_llm_field_extraction_chunks(
        ["a", "b"],
        ["f"],
        workers=4,
        api_key="k",
        base_url="https://example.com/v1",
        model="m",
        timeout_sec=30,
        extraction_fn=fake_one,
    )
    assert merged["f"]["value"] == "chunk0\nchunk1"


def test_parallel_chunk_worker_error_keeps_other_parts() -> None:

    def fake_one(text: str, field_names: list[str], **kwargs: object):
        if text == "a":
            raise RuntimeError("simulated network failure")
        if text == "b":
            return ({"f": {"value": "ok", "evidence_paragraphs": [], "confidence": 0.5}}, [])
        return ({}, [])

    merged, warns = llm_engine._run_llm_field_extraction_chunks(
        ["a", "b"],
        ["f"],
        workers=4,
        api_key="k",
        base_url="https://example.com/v1",
        model="m",
        timeout_sec=30,
        extraction_fn=fake_one,
    )
    assert merged["f"]["value"] == "ok"
    assert any("llm_field_refine_chunk_worker_error:RuntimeError" in w for w in warns)


def test_run_llm_field_extraction_adds_parallel_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("FIELD_REFINE_USE_CHUNKS", "true")
    monkeypatch.setenv("FIELD_REFINE_MAX_CHUNKS", "8")
    monkeypatch.setattr(llm_engine, "_field_refine_chunk_size", lambda: 1)
    monkeypatch.setattr(llm_engine, "_field_refine_chunk_max_workers", lambda: 3)

    def fake_one(text: str, field_names: list[str], **kwargs: object):
        return ({"f": {"value": text, "evidence_paragraphs": [], "confidence": 0.9}}, [])

    monkeypatch.setattr(llm_engine, "_run_llm_field_extraction_one", fake_one)
    _merged, warns = llm_engine.run_llm_field_extraction("xy", ["f"])
    assert any(w == "llm_field_refine_chunk_parallel:3" for w in warns)
