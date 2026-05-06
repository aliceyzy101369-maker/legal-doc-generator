"""Dify-oriented acceptance fixtures — stub LLM, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dify_cases"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "stub")
    monkeypatch.setenv("CONTRACT_DOCUMENT_PROVIDER", "stub")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _cases():
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", list(_cases()), ids=lambda c: c["slug"])
def test_review_case_fixture(client: TestClient, case: dict) -> None:
    resp = client.post("/reviews", json=case["input"])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["fields"]) >= case["expected_min_fields"]
    assert len(body["issues"]) >= case["expected_min_issues"]
    s = body["summary"]
    for key in case["expected_summary_keys"]:
        assert key in s
    assert "final_output" in body


@pytest.mark.parametrize("case", list(_cases()), ids=lambda c: c["slug"] + "_dry")
def test_dry_run_case_fixture(client: TestClient, case: dict) -> None:
    resp = client.post("/reviews/dry-run", json=case["input"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["review_task_count"] > 0
    if case["slug"] == "case_markdown_lines":
        assert body["summary"].get("input_parse_mode") == "markdown_lines"
        assert body["summary"].get("markdown_line_count", 0) >= 2
        assert "markdown_line_records" in body["summary"]
