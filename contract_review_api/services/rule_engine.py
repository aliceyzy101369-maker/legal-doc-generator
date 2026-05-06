from __future__ import annotations

from typing import Dict, List

from contract_review_api.core.models import FieldCandidate, ReviewIssue


REQUIRED_FIELDS = ("project_name", "party_info", "effective_period")


def run_rule_review(fields: List[FieldCandidate]) -> List[ReviewIssue]:
    issues: List[ReviewIssue] = []
    index: Dict[str, FieldCandidate] = {f.field_key: f for f in fields}

    for key in REQUIRED_FIELDS:
        if key not in index or not index[key].value.strip():
            issues.append(
                ReviewIssue(
                    title=f"{key} missing",
                    comment=f"Required field `{key}` is not found in contract content.",
                    degree="高",
                    category=0,
                    evidence=[],
                )
            )

    period = index.get("effective_period")
    if period and "至" not in period.value:
        issues.append(
            ReviewIssue(
                title="effective period format risk",
                comment="Effective period text is found but does not contain a complete start/end boundary.",
                degree="中",
                category=0,
                evidence=period.evidence_paragraphs,
            )
        )
    return issues


def build_default_review_rules() -> List[dict]:
    return [
        {
            "title": "project_name",
            "instruction": "检查项目名称是否存在并与合同主题一致。",
            "outputs": ["risk"],
            "risk_level": "高",
            "empty_policy": 1,
            "target_fields": [{"name": "project_name", "desc": "项目名称", "src": 1, "mode": 1}],
        },
        {
            "title": "party_info",
            "instruction": "检查甲乙方主体信息是否完整，是否可唯一识别。",
            "outputs": ["risk"],
            "risk_level": "高",
            "empty_policy": 1,
            "target_fields": [{"name": "party_info", "desc": "合同主体信息", "src": 1, "mode": 1}],
        },
        {
            "title": "effective_period",
            "instruction": "检查合同期限是否包含完整起止边界。",
            "outputs": ["risk"],
            "risk_level": "中",
            "empty_policy": 1,
            "target_fields": [{"name": "effective_period", "desc": "合同期限", "src": 1, "mode": 1}],
        },
    ]
