from contract_review_api.core.models import FieldCandidate
from contract_review_api.services.review_task_builder import build_review_tasks


def test_build_review_tasks_skips_empty_policy_rules():
    fields = [FieldCandidate(field_key="project_name", value="", confidence=0.8)]
    rules = [
        {
            "title": "project_name",
            "instruction": "check",
            "outputs": [],
            "risk_level": "高",
            "empty_policy": 1,
            "target_fields": [{"name": "project_name", "desc": "项目名称", "src": 1, "mode": 1}],
        }
    ]
    tasks = build_review_tasks(fields, rules, limit=50)
    assert tasks == []


def test_build_review_tasks_keeps_anchor_group_together():
    fields = [FieldCandidate(field_key="contract_type", value="买卖合同", confidence=0.9)]
    rules = [
        {
            "title": "合同类型",
            "instruction": "anchor instruction",
            "outputs": [],
            "risk_level": "中",
            "empty_policy": 0,
            "target_fields": [{"name": "合同类型", "desc": "来自字段解释", "src": 0, "mode": 1}],
        },
        {
            "title": "other_rule",
            "instruction": "x" * 200,
            "outputs": [],
            "risk_level": "低",
            "empty_policy": 0,
            "target_fields": [{"name": "contract_type", "desc": "合同类型", "src": 1, "mode": 1}],
        },
    ]
    tasks = build_review_tasks(fields, rules, limit=120)
    assert len(tasks) >= 1
    assert tasks[0]["审查规则"][0]["审查项标题"] == "合同类型"
    assert "合同类型：" in tasks[0]["待审文本"]
