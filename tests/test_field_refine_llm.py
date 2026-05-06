import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.core.models import FieldCandidate, Paragraph
from contract_review_api.services import field_extraction


def test_rules_mode_default_unchanged():
    coarse = [
        FieldCandidate(field_key="party_info", value="甲方：A", confidence=0.65, evidence_paragraphs=[1]),
    ]
    rules = [{"target_fields": [{"name": "project_name", "src": 1, "mode": 1}]}]
    merged, warnings = field_extraction.refine_field_candidates(
        coarse, rules, contract_type_override=None, contract_text="合同全文"
    )
    keys = {f.field_key for f in merged}
    assert "party_info" in keys
    assert "project_name" in keys
    assert not any("llm_field" in w for w in warnings)


def test_llm_mode_merge_prefers_non_empty_llm(monkeypatch):
    monkeypatch.setenv("FIELD_REFINE_MODE", "llm")

    def fake_llm(_text: str, _names: list[str]):
        return (
            {
                "party_info": {
                    "value": "甲方：北京全称公司；乙方：上海全称公司",
                    "evidence_paragraphs": [1],
                    "confidence": 0.9,
                }
            },
            [],
        )

    monkeypatch.setattr(field_extraction, "run_llm_field_extraction", fake_llm)

    paras = [Paragraph("r1", "main", 1, "甲方：简写\n乙方：简写")]
    coarse = field_extraction.extract_field_candidates_coarse(paras)
    rules = [{"target_fields": [{"name": "party_info", "src": 1, "mode": 1}]}]
    merged, _w = field_extraction.refine_field_candidates(
        coarse, rules, contract_type_override=None, contract_text="甲方：简写\n乙方：简写"
    )
    party = next(f for f in merged if f.field_key == "party_info")
    assert "全称" in party.value
    assert "\n" in party.value  # LLM 精提与粗提同字段按 \\n 拼接，不覆盖
    assert party.evidence_paragraphs == [1]


def test_llm_field_refine_env_alias(monkeypatch):
    monkeypatch.delenv("FIELD_REFINE_MODE", raising=False)
    monkeypatch.setenv("LLM_FIELD_REFINE", "true")

    def fake_llm(_text: str, _names: list[str]):
        return ({"project_name": {"value": "LLM项目", "evidence_paragraphs": [], "confidence": 0.88}}, [])

    monkeypatch.setattr(field_extraction, "run_llm_field_extraction", fake_llm)

    coarse: list[FieldCandidate] = []
    rules = [{"target_fields": [{"name": "project_name", "src": 1, "mode": 1}]}]
    merged, warnings = field_extraction.refine_field_candidates(
        coarse, rules, contract_text="项目名称：正则未命中"
    )
    assert "coarse_field_extraction_empty" in warnings
    proj = next(f for f in merged if f.field_key == "project_name")
    assert proj.value == "LLM项目"


def test_llm_mode_stub_returns_no_llm_map(monkeypatch):
    """LLM_MODE=stub: field extraction does not call HTTP; coarse + gap-fill remain."""
    monkeypatch.setenv("FIELD_REFINE_MODE", "llm")
    monkeypatch.setenv("LLM_MODE", "stub")

    paras = [Paragraph("r1", "main", 1, "项目名称：采购")]
    coarse = field_extraction.extract_field_candidates_coarse(paras)
    rules = [{"target_fields": [{"name": "party_info", "src": 1, "mode": 1}]}]
    merged, warnings = field_extraction.refine_field_candidates(
        coarse, rules, contract_text="项目名称：采购"
    )
    assert not any(w.startswith("llm_field_refine_") for w in warnings)
    keys = {f.field_key for f in merged}
    assert "project_name" in keys
    assert "party_info" in keys
