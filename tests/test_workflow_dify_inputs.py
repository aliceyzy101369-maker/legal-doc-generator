"""Dify workflow §2.2 optional inputs → source_library slots."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app


@pytest.fixture(autouse=True)
def _llm_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "stub")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_contract_subject_goes_to_source_library_src1(client: TestClient) -> None:
    resp = client.post(
        "/reviews/dry-run",
        json={
            "text": "甲方：北京甲公司\n乙方：上海乙公司\n项目名称：X\n自2026年1月1日至2026年12月31日",
            "ruleset_ids": ["demo"],
            "contract_subject": "主体行：法定代表人张某",
        },
    )
    assert resp.status_code == 200
    lib = resp.json()["summary"]["source_library"]
    src1 = next(x for x in lib if x["src"] == 1)
    assert "法定代表人" in src1["content"]


def test_business_info_and_enterprise_list_merge_to_src4(client: TestClient) -> None:
    resp = client.post(
        "/reviews/dry-run",
        json={
            "text": "甲方：A\n乙方：B\n项目名称：P\n自2026年1月1日至2026年12月31日",
            "ruleset_ids": ["demo"],
            "business_info": "统一社会信用代码 91110000",
            "enterprise_list": '[{"name":"子公司"}]',
        },
    )
    assert resp.status_code == 200
    lib = resp.json()["summary"]["source_library"]
    src4 = next(x for x in lib if x["src"] == 4)
    assert "91110000" in src4["content"] and "子公司" in src4["content"]


def test_summary_includes_source_slot_lens(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={
            "text": "甲方：A\n乙方：B\n项目名称：P\n自2026年1月1日至2026年12月31日",
            "ruleset_ids": ["demo"],
            "contract_subject": "subj",
            "business_info": "biz",
        },
    )
    assert resp.status_code == 200
    lens = resp.json()["summary"]["source_slot_lens"]
    assert lens["src1_contract_subject"] == 4
    assert lens["src4_business_slot"] == 3
