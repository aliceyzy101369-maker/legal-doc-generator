import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app


client = TestClient(app)


def test_review_from_text():
    payload = {
        "text": "甲方：北京甲公司\n\n乙方：上海乙公司\n\n项目名称：货物采购\n\n合同类型：买卖合同\n\n自2026年1月1日至2026年12月31日",
        "ruleset_ids": ["demo"],
        "user_position": "受让人",
    }
    resp = client.post("/reviews", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["review_id"]
    assert "summary" in body
    assert "review_task_count" in body["summary"]
    assert "rules_loaded_count" in body["summary"]
    assert "fields" in body
    assert "issues" in body
    assert "final_output" in body
    assert "comment_list" in body["final_output"]
    assert "extracted_info" in body["final_output"]
    for item in body["final_output"]["comment_list"]:
        assert len(item.keys()) in (4, 7)


def test_review_requires_source():
    resp = client.post("/reviews", json={"ruleset_ids": ["demo"]})
    assert resp.status_code == 400


def test_final_output_extracted_info_contains_key_value_pairs():
    payload = {
        "text": "甲方：北京甲公司\n\n乙方：上海乙公司\n\n项目名称：货物采购\n\n合同类型：买卖合同\n\n自2026年1月1日至2026年12月31日",
        "ruleset_ids": ["demo"],
    }
    resp = client.post("/reviews", json=payload)
    assert resp.status_code == 200
    data = resp.json()["final_output"]["extracted_info"]
    assert isinstance(data, list)
    assert all("title" in item and "comment" in item for item in data)


def test_review_from_file_path(tmp_path):
    contract_file = tmp_path / "contract.txt"
    contract_file.write_text(
        "甲方：北京甲公司\n乙方：上海乙公司\n项目名称：货物采购\n合同类型：买卖合同\n自2026年1月1日至2026年12月31日",
        encoding="utf-8",
    )
    resp = client.post("/reviews", json={"file_path": str(contract_file), "ruleset_ids": ["demo"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["fields"]


def test_review_rejects_unsupported_file_type(tmp_path):
    unsupported_file = tmp_path / "contract.csv"
    unsupported_file.write_text("a,b,c\n1,2,3", encoding="utf-8")
    resp = client.post("/reviews", json={"file_path": str(unsupported_file), "ruleset_ids": ["demo"]})
    assert resp.status_code == 422


def test_review_rejects_unknown_ruleset():
    payload = {
        "text": "甲方：北京甲公司\n乙方：上海乙公司\n项目名称：货物采购\n自2026年1月1日至2026年12月31日",
        "ruleset_ids": ["not-exists"],
    }
    resp = client.post("/reviews", json=payload)
    assert resp.status_code == 400


def test_list_rulesets_endpoint():
    resp = client.get("/rulesets")
    assert resp.status_code == 200
    body = resp.json()
    assert "ruleset_ids" in body
    assert "base-rules" in body["ruleset_ids"]


def test_review_dry_run_endpoint():
    payload = {
        "text": "甲方：北京甲公司\n乙方：上海乙公司\n项目名称：货物采购\n自2026年1月1日至2026年12月31日",
        "ruleset_ids": ["base-rules"],
    }
    resp = client.post("/reviews/dry-run", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert "review_tasks" in body
    assert "rules_loaded_count" in body["summary"]
    s = body["summary"]
    assert "pending_object_field_library" in s and len(s["pending_object_field_library"]) >= 1
    assert "source_library" in s and len(s["source_library"]) == 4
    assert "source_library_meta" in s and len(s["source_library_meta"]) == 4
    assert "field_extraction_tasks" in s
    assert set(s["field_extraction_tasks"].keys()) == {"mode_1", "mode_23"}
    assert "field_extraction_task_counts" in s
