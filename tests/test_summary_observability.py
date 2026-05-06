from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.core import pipeline as pipeline_mod
from contract_review_api.main import app
from contract_review_api.services import llm_engine


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "stub")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_summary_contains_trace_and_counts(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={
            "text": "甲方：X\n\n乙方：Y\n\n项目名称：Z\n\n自2026年1月1日至2026年12月31日",
            "ruleset_ids": ["demo"],
            "trace_id": "trace-integration-1",
        },
    )
    assert resp.status_code == 200
    s = resp.json()["summary"]
    for key in (
        "trace_id",
        "field_count",
        "rules_loaded_count",
        "review_task_count",
        "issue_count",
        "llm_call_count",
        "success_count",
        "error_count",
        "degraded_count",
        "chunk_count",
        "attachment_count",
        "coarse_field_count",
        "refined_field_count",
        "review_max_workers",
        "aggregation_success_count",
        "aggregation_error_count",
    ):
        assert key in s
    assert s["trace_id"] == "trace-integration-1"
    assert s["attachment_count"] == 0


def test_degraded_count_when_llm_returns_degraded(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(
        pipeline_mod,
        "run_llm_review",
        lambda *a, **k: llm_engine.degraded_llm_issues("forced"),
    )
    monkeypatch.setattr(
        pipeline_mod,
        "run_llm_review_with_debug",
        lambda *a, **k: {"issues": llm_engine.degraded_llm_issues("forced"), "fallback_reason": "x", "raw_output": ""},
    )
    resp = client.post(
        "/reviews",
        json={"text": "甲方：A\n\n乙方：B\n\n项目名称：C\n\n自2026年1月1日至2026年12月31日", "ruleset_ids": ["demo"]},
    )
    assert resp.status_code == 200
    assert resp.json()["summary"]["degraded_count"] >= 1
