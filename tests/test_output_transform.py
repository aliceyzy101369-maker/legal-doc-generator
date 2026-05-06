from contract_review_api.core.models import FieldCandidate, ReviewIssue
from contract_review_api.services.output_transform import build_final_output, normalize_review_issues


def test_build_final_output_normalizes_category_and_original_id():
    fields = [FieldCandidate(field_key="contract_type", value="买卖合同", confidence=0.9)]
    issues = [
        ReviewIssue(
            title="缺失条款",
            comment="建议补充违约责任",
            degree="高",
            category=1,
            change_type="新增",
            revised_text="12##text##*补充违约责任*",
            evidence=[12, 13],
        ),
        ReviewIssue(
            title="风险提示",
            comment="措辞偏弱",
            degree="低",
            category=9,
            revised_text="不应输出",
            evidence=[99],
        ),
    ]
    out = build_final_output(fields, issues)
    assert len(out.comment_list) == 2

    amend = out.comment_list[0]
    assert amend.category == 1
    assert amend.change_type == "新增"
    assert amend.original_id == [1]
    assert amend.revised_text == "补充违约责任"

    risk = out.comment_list[1]
    assert risk.category == 0
    assert risk.change_type is None
    assert risk.original_id is None
    assert risk.revised_text is None


def test_build_final_output_extracted_info_is_cleaned():
    fields = [FieldCandidate(field_key="test_field", value="8##text##_值_", confidence=0.8)]
    out = build_final_output(fields, [])
    assert out.extracted_info[0].title == "test_field"
    assert out.extracted_info[0].comment == "值"


def test_build_final_output_enforces_4_or_7_key_shape():
    issues = [
        ReviewIssue(title="r1", comment="c1", degree="中", category=0),
        ReviewIssue(title="r2", comment="c2", degree="高", category=1, change_type="未知"),
    ]
    out = build_final_output([], issues)
    dumped = out.model_dump(exclude_none=True)
    keys0 = set(dumped["comment_list"][0].keys())
    keys1 = set(dumped["comment_list"][1].keys())
    assert keys0 == {"title", "comment", "degree", "category"}
    assert keys1 == {"title", "comment", "degree", "category", "change_type", "original_id", "revised_text"}
    assert dumped["comment_list"][1]["change_type"] == "新增"


def test_normalize_review_issues_enforces_key_shape_and_cleaning():
    raw_issues = [
        {
            "title": "risk",
            "comment": "weak clause",
            "degree": "低",
            "category": 9,  # forced to 0
            "change_type": "删除",
            "original_id": [3],
            "revised_text": "*no*",
        },
        {
            "title": "amend",
            "comment": "should revise",
            "degree": "高",
            "category": 1,
            "change_type": "非法值",  # forced to 新增
            "original_id": None,  # fallback to [1]
            "revised_text": "12##text##*补充违约责任*",
        },
        123,  # non-dict element should be skipped
    ]

    out = normalize_review_issues(raw_issues)
    assert len(out) == 2

    keys0 = set(out[0].keys())
    keys1 = set(out[1].keys())
    assert keys0 == {"title", "comment", "degree", "category"}
    assert keys1 == {"title", "comment", "degree", "category", "change_type", "original_id", "revised_text"}
    assert out[1]["change_type"] == "新增"
    assert out[1]["original_id"] == [1]
    assert out[1]["revised_text"] == "补充违约责任"
