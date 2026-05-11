"""集成测试：用一份有问题的合同跑完整审查流程（强制 stub LLM，避免外网）"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app

PROBLEMATIC_CONTRACT = """
甲方：北京甲公司

乙方：上海乙公司

项目名称：企业采购系统实施服务

合同类型：服务合同

合同总价：人民币120万元

付款方式：双方另行协商。

交付时间：乙方应尽快交付系统并完成部署。

验收标准：以甲方满意为准。

违约责任：双方友好协商解决，不承担其他责任。

争议解决：未约定。

保密条款：双方应对合作信息保密。

知识产权：乙方交付成果相关权利归属未明确。

地址：北京市朝阳区XX路88号

合同期限：自2026年1月1日至2026年12月31日。
"""


@pytest.fixture(autouse=True)
def _force_stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "stub")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_main_chain_structure(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["base-rules"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    fo = body["final_output"]
    assert "comment_list" in fo and "extracted_info" in fo


def test_field_extraction_coverage(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["base-rules"]},
    )
    assert resp.status_code == 200
    titles = {x["title"] for x in resp.json()["final_output"]["extracted_info"]}
    assert len(titles) >= 3


def test_dry_run_returns_tasks(client: TestClient) -> None:
    resp = client.post(
        "/reviews/dry-run",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["base-rules"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "review_tasks" in body and "summary" in body
    assert len(body["review_tasks"]) > 0


def test_empty_text_rejected(client: TestClient) -> None:
    resp = client.post("/reviews", json={"text": "", "ruleset_ids": ["base-rules"]})
    assert resp.status_code in (400, 422)


def test_unknown_ruleset_rejected(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["不存在的"]},
    )
    assert resp.status_code == 400


def test_comment_list_key_shapes(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["base-rules"]},
    )
    assert resp.status_code == 200
    for item in resp.json()["final_output"]["comment_list"]:
        cat = item["category"]
        keys = set(item.keys())
        if cat == 0:
            assert keys == {"title", "comment", "degree", "category"}
        elif cat == 1:
            assert keys == {"title", "comment", "degree", "category", "change_type", "original_id", "revised_text"}


def test_extracted_info_items_have_title_comment(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["base-rules"]},
    )
    assert resp.status_code == 200
    for row in resp.json()["final_output"]["extracted_info"]:
        assert set(row.keys()) == {"title", "comment"}


def test_summary_fields(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"text": PROBLEMATIC_CONTRACT, "ruleset_ids": ["base-rules"]},
    )
    assert resp.status_code == 200
    s = resp.json()["summary"]
    for key in (
        "field_count",
        "rules_loaded_count",
        "review_task_count",
        "issue_count",
        "trace_id",
        "llm_call_count",
        "degraded_count",
        "chunk_count",
        "attachment_count",
        "coarse_field_count",
        "refined_field_count",
        "review_max_workers",
        "aggregation_success_count",
        "aggregation_error_count",
        "pending_object_field_library",
        "source_library_meta",
        "field_extraction_task_counts",
        "source_slot_lens",
        "error_collection",
    ):
        assert key in s
