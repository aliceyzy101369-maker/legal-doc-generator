from contract_review_api.core.models import FieldCandidate
from contract_review_api.services.result_merge import merge_fields


def test_merge_fields_concat_same_key_in_order():
    cands = [
        FieldCandidate(field_key="party_info", value="甲方A", confidence=0.5, evidence_paragraphs=[1]),
        FieldCandidate(field_key="party_info", value="乙方B", confidence=0.6, evidence_paragraphs=[2]),
    ]
    out = merge_fields(cands)
    assert len(out) == 1
    assert out[0].field_key == "party_info"
    assert out[0].value == "甲方A\n乙方B"
    assert sorted(out[0].evidence_paragraphs) == [1, 2]


def test_merge_fields_contract_type_override_replaces_extracted():
    cands = [
        FieldCandidate(field_key="contract_type", value="买卖合同", confidence=0.7, evidence_paragraphs=[3]),
    ]
    out = merge_fields(cands, contract_type_override="服务合同")
    assert len(out) == 1
    assert out[0].value == "服务合同"


def test_merge_fields_contract_type_override_when_missing_extracted():
    cands = [FieldCandidate(field_key="project_name", value="X", confidence=0.8, evidence_paragraphs=[1])]
    out = merge_fields(cands, contract_type_override="补充协议")
    keys = {x.field_key for x in out}
    assert "contract_type" in keys
    ct = next(x for x in out if x.field_key == "contract_type")
    assert ct.value == "补充协议"
