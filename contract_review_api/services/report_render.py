from __future__ import annotations

from typing import List

from contract_review_api.core.models import FieldCandidate, ReviewIssue


def render_markdown(fields: List[FieldCandidate], issues: List[ReviewIssue], review_id: str) -> str:
    lines: List[str] = [f"# Contract Review Report", f"", f"- review_id: `{review_id}`", ""]

    lines.append("## Extracted Fields")
    if not fields:
        lines.append("- (none)")
    for field in fields:
        lines.append(
            f"- `{field.field_key}`: {field.value or '(empty)'} "
            f"(confidence={field.confidence:.2f}, evidence={field.evidence_paragraphs})"
        )

    lines.append("")
    lines.append("## Review Issues")
    if not issues:
        lines.append("- (none)")
    for issue in issues:
        lines.append(f"- [{issue.degree}] {issue.title}: {issue.comment}")
    lines.append("")
    return "\n".join(lines)


def build_summary(
    fields: List[FieldCandidate],
    issues: List[ReviewIssue],
    elapsed_ms: int,
    review_task_count: int = 0,
    rules_loaded_count: int = 0,
) -> dict:
    return {
        "field_count": len(fields),
        "issue_count": len(issues),
        "high_risk_count": len([i for i in issues if i.degree == "高"]),
        "review_task_count": review_task_count,
        "rules_loaded_count": rules_loaded_count,
        "elapsed_ms": elapsed_ms,
    }
