from __future__ import annotations

import hashlib
from typing import Dict, List

from contract_review_api.core.models import FieldCandidate, ReviewIssue


def merge_fields(candidates: List[FieldCandidate]) -> List[FieldCandidate]:
    merged: Dict[str, FieldCandidate] = {}
    for item in candidates:
        existing = merged.get(item.field_key)
        if not existing:
            merged[item.field_key] = item
            continue
        # non-empty and higher confidence takes priority
        if _is_better(item, existing):
            merged[item.field_key] = item
    return list(merged.values())


def merge_issues(rule_issues: List[ReviewIssue], llm_issues: List[ReviewIssue]) -> List[ReviewIssue]:
    out: Dict[str, ReviewIssue] = {}
    for issue in [*rule_issues, *llm_issues]:
        if not issue.title and not issue.comment:
            continue
        key = _issue_key(issue)
        if key not in out:
            out[key] = issue
            continue
        # keep higher degree severity if duplicated
        if _severity(issue.degree) > _severity(out[key].degree):
            out[key] = issue
    return sorted(out.values(), key=lambda x: _severity(x.degree), reverse=True)


def _is_better(left: FieldCandidate, right: FieldCandidate) -> bool:
    if left.value and not right.value:
        return True
    if not left.value and right.value:
        return False
    if left.confidence != right.confidence:
        return left.confidence > right.confidence
    return len(left.value) > len(right.value)


def _issue_key(issue: ReviewIssue) -> str:
    raw = f"{issue.title}|{issue.category}|{issue.change_type}|{issue.revised_text or ''}|{issue.comment}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _severity(degree: str) -> int:
    mapping = {"高": 4, "中": 3, "低": 2, "无风险": 1}
    return mapping.get(degree, 0)
