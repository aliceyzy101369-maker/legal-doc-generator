from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Dict, List

from contract_review_api.core.models import FieldCandidate, ReviewIssue


def merge_fields(
    candidates: List[FieldCandidate],
    *,
    contract_type_override: str | None = None,
) -> List[FieldCandidate]:
    """
    Merge field candidates:
    - Same field_key: concatenate non-empty values in encounter order with '\\n' (Dify 合流语义).
    - contract_type: if contract_type_override is provided, ignore extracted values and use override only.
    - If override is provided but no extracted contract_type exists, append a synthetic field.
    """
    if not candidates:
        return []

    buckets: defaultdict[str, list[FieldCandidate]] = defaultdict(list)
    key_order: list[str] = []
    for item in candidates:
        if item.field_key not in buckets:
            key_order.append(item.field_key)
        buckets[item.field_key].append(item)

    out: list[FieldCandidate] = []
    override = str(contract_type_override or "").strip()

    for key in key_order:
        items = buckets[key]
        if key == "contract_type" and override:
            max_conf = max((x.confidence for x in items), default=0.0)
            evidence = sorted({p for x in items for p in x.evidence_paragraphs})
            out.append(
                FieldCandidate(
                    field_key=key,
                    value=override,
                    confidence=max(max_conf, 0.95),
                    evidence_paragraphs=evidence,
                )
            )
            continue

        parts: list[str] = []
        for it in items:
            v = str(it.value or "").strip()
            if not v:
                continue
            parts.append(v)
        value = "\n".join(parts)
        max_conf = max((x.confidence for x in items), default=0.0)
        evidence = sorted({p for x in items for p in x.evidence_paragraphs})
        out.append(FieldCandidate(field_key=key, value=value, confidence=max_conf, evidence_paragraphs=evidence))

    if override and "contract_type" not in key_order:
        out.append(FieldCandidate(field_key="contract_type", value=override, confidence=0.95, evidence_paragraphs=[]))

    return out


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


def _issue_key(issue: ReviewIssue) -> str:
    raw = f"{issue.title}|{issue.category}|{issue.change_type}|{issue.revised_text or ''}|{issue.comment}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _severity(degree: str) -> int:
    mapping = {"高": 4, "中": 3, "低": 2, "无风险": 1}
    return mapping.get(degree, 0)
