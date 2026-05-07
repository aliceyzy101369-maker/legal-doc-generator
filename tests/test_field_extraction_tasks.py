from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.field_extraction_tasks import (
    build_field_extraction_task_split,
    enrich_field_extraction_tasks_with_sources,
)


def test_split_mode_1_vs_23() -> None:
    pending = [
        {"name": "a", "mode": 1, "src": 1},
        {"name": "b", "mode": 23, "src": 1},
        {"name": "c", "mode": 2, "src": 1},
        {"name": "d", "mode": 3, "src": 2},
    ]
    out = build_field_extraction_task_split(pending)
    assert [x["name"] for x in out["mode_1"]] == ["a"]
    assert {x["name"] for x in out["mode_23"]} == {"b", "c", "d"}


def test_unknown_mode_defaults_to_mode_1() -> None:
    out = build_field_extraction_task_split([{"name": "x", "mode": 99, "src": 1}])
    assert [x["name"] for x in out["mode_1"]] == ["x"]


def test_enrich_attaches_source_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS", "5")
    tasks = {"mode_1": [{"name": "f", "mode": 1, "src": 2}], "mode_23": []}
    lib = [{"src": 2, "content": "abcdefghij"}]
    out = enrich_field_extraction_tasks_with_sources(tasks, lib)
    row = out["mode_1"][0]
    assert row["source_matched_src"] == 2
    assert row["source_full_len"] == 10
    assert row["source_preview"] == "abcde"
    assert row["source_preview_truncated"] is True


def test_enrich_preview_zero_omits_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS", "0")
    tasks = {"mode_1": [{"name": "f", "mode": 1, "src": 1}], "mode_23": []}
    lib = [{"src": 1, "content": "xyz"}]
    out = enrich_field_extraction_tasks_with_sources(tasks, lib)
    row = out["mode_1"][0]
    assert row["source_preview"] == ""
    assert row["source_full_len"] == 3
