"""Golden-style regression: stub LLM, bounds on summary counts (no full-text asserts)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "golden"
GOLDEN_CASE_FILES = ("sample_purchase.json", "sample_service.json")


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "stub")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _load_case(filename: str) -> dict:
    path = FIXTURES / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _post_review(client: TestClient, text: str, ruleset_ids: list[str]) -> dict:
    r = client.post("/reviews", json={"text": text, "ruleset_ids": ruleset_ids})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("case_file", GOLDEN_CASE_FILES)
def test_golden_fixture_summary_bounds(client: TestClient, case_file: str) -> None:
    case = _load_case(case_file)
    text = str(case.get("text") or "").strip()
    ruleset_ids = case.get("ruleset_ids") or ["demo"]
    exp = case.get("expect") or {}
    assert text, case_file
    body = _post_review(client, text, list(ruleset_ids))
    s = body["summary"]
    assert exp["field_count_min"] <= s["field_count"] <= exp["field_count_max"]
    assert exp["issue_count_min"] <= s["issue_count"] <= exp["issue_count_max"]
    assert (
        exp["aggregation_success_count_min"]
        <= s["aggregation_success_count"]
        <= exp["aggregation_success_count_max"]
    )
    assert isinstance(s.get("error_collection"), list)
