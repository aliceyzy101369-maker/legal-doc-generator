from contract_review_api.core.models import FieldCandidate, ReviewIssue
from contract_review_api.services.result_merge import (
    issues_for_error_collection,
    merge_fields,
    merge_issues,
    partition_issues_for_final_output,
)


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


def test_merge_issues_dedupes_by_title_and_comment():
    a = ReviewIssue(title="付款", comment="模糊", degree="高", category=0, evidence=[])
    b = ReviewIssue(title="付款", comment="模糊", degree="中", category=0, evidence=[])
    out = merge_issues([a], [b])
    assert len(out) == 1
    assert out[0].degree == "高"


def test_merge_issues_sorts_by_severity_then_title():
    low = ReviewIssue(title="Z", comment="z", degree="低", category=0, evidence=[])
    high = ReviewIssue(title="A", comment="a", degree="高", category=0, evidence=[])
    mid = ReviewIssue(title="B", comment="b", degree="中", category=0, evidence=[])
    out = merge_issues([low, high, mid], [])
    assert [x.degree for x in out] == ["高", "中", "低"]
    assert out[0].title == "A"


def test_partition_moves_llm_degraded_only():
    good = ReviewIssue(title="风险", comment="x", degree="中", category=0, evidence=[])
    bad = ReviewIssue(title="模型审查降级提示", comment="y", degree="低", category=0, evidence=[])
    bootstrap = ReviewIssue(title="字段粗提降级提示", comment="z", degree="低", category=0, evidence=[])
    g, d = partition_issues_for_final_output([good, bad, bootstrap])
    assert len(g) == 2 and {x.title for x in g} == {"风险", "字段粗提降级提示"}
    assert len(d) == 1 and d[0].title == "模型审查降级提示"


def test_issues_for_error_collection_shape():
    bad = ReviewIssue(title="模型审查降级提示", comment="y", degree="低", category=0, evidence=[3])
    rows = issues_for_error_collection([bad])
    assert rows == [
        {
            "title": "模型审查降级提示",
            "comment": "y",
            "degree": "低",
            "category": 0,
            "change_type": None,
            "evidence": [3],
            "source": "llm_subtask",
        }
    ]


def test_issues_for_error_collection_respects_error_source():
    doc = ReviewIssue(
        title="模型审查降级提示",
        comment="attachment_not_found:x",
        degree="低",
        category=0,
        evidence=[],
        error_source="document_fetch",
    )
    rows = issues_for_error_collection([doc])
    assert rows[0]["source"] == "document_fetch"
