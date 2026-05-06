"""Remote id resolution (stub provider) + attachment merge — stub LLM."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "stub")
    monkeypatch.setenv("CONTRACT_DOCUMENT_PROVIDER", "stub")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_main_contract_id_only(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"contract_id": "main-contract-stub", "ruleset_ids": ["demo"]},
    )
    assert resp.status_code == 200
    assert resp.json()["summary"]["attachment_count"] == 0


def test_main_plus_remote_attachments(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={
            "contract_id": "main-contract-stub",
            "attachment_ids": ["att-stub-1", "att-stub-2"],
            "ruleset_ids": ["demo"],
        },
    )
    assert resp.status_code == 200
    s = resp.json()["summary"]
    assert s["attachment_count"] == 2


def test_missing_attachment_id_soft_warning(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={
            "contract_id": "main-contract-stub",
            "attachment_ids": ["does-not-exist"],
            "ruleset_ids": ["demo"],
        },
    )
    assert resp.status_code == 200
    warns = resp.json()["summary"].get("input_warnings", [])
    assert any("attachment_not_found" in w for w in warns)


def test_local_main_plus_local_attachment(tmp_path: Path, client: TestClient) -> None:
    main = tmp_path / "m.txt"
    main.write_text("甲方：A公司\n\n乙方：B公司\n\n项目名称：本地主合同\n\n自2026年1月1日至2026年12月31日", encoding="utf-8")
    att = tmp_path / "a.txt"
    att.write_text("附件：补充说明一行。", encoding="utf-8")
    resp = client.post(
        "/reviews",
        json={"file_path": str(main), "attachment_paths": [str(att)], "ruleset_ids": ["demo"]},
    )
    assert resp.status_code == 200
    assert resp.json()["summary"]["attachment_count"] == 1


def test_document_id_not_found_400(client: TestClient) -> None:
    resp = client.post(
        "/reviews",
        json={"main_contract_id": "unknown-id-xyz", "ruleset_ids": ["demo"]},
    )
    assert resp.status_code == 400


def test_null_provider_rejects_ids(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CONTRACT_DOCUMENT_PROVIDER", "none")
    resp = client.post(
        "/reviews",
        json={"contract_id": "main-contract-stub", "ruleset_ids": ["demo"]},
    )
    assert resp.status_code == 400
