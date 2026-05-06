"""FIELD_REFINE_MODE=regex: no LLM field extraction call."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.core.models import FieldCandidate
from contract_review_api.services import field_extraction


def test_regex_mode_does_not_call_llm_field_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELD_REFINE_MODE", "regex")
    monkeypatch.delenv("LLM_FIELD_REFINE", raising=False)

    called: list[bool] = []

    def boom(_text: str, _names: list[str]):
        called.append(True)
        return ({}, [])

    monkeypatch.setattr(field_extraction, "run_llm_field_extraction", boom)

    coarse = [
        FieldCandidate(field_key="party_info", value="甲方：A", confidence=0.65, evidence_paragraphs=[1]),
    ]
    rules = [{"target_fields": [{"name": "project_name", "src": 1, "mode": 1}]}]
    field_extraction.refine_field_candidates(
        coarse,
        rules,
        contract_type_override=None,
        contract_text="全文",
        source_library=[{"src": 1, "content": "x"}],
    )
    assert called == []
