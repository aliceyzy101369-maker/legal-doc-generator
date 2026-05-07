from __future__ import annotations

from typing import List

from contract_review_api.core.models import FieldCandidate, ReviewIssue


def render_markdown(
    fields: List[FieldCandidate],
    issues: List[ReviewIssue],
    review_id: str,
    *,
    final_comment_count: int | None = None,
    extracted_info_count: int | None = None,
) -> str:
    lines: List[str] = [
        "# 合同审查报告",
        "",
        f"- **review_id**: `{review_id}`",
    ]
    if final_comment_count is not None:
        lines.append(f"- **标准化审查意见条数**（final_output.comment_list）: {final_comment_count}")
    if extracted_info_count is not None:
        lines.append(f"- **提取信息条数**（final_output.extracted_info）: {extracted_info_count}")
    lines.append("")

    lines.append("## 提取字段（合并后）")
    if not fields:
        lines.append("- （无）")
    for field in fields:
        lines.append(
            f"- `{field.field_key}`: {field.value or '（空）'} "
            f"（confidence={field.confidence:.2f}，evidence={field.evidence_paragraphs}）"
        )

    lines.append("")
    lines.append("## 审查问题（含规则 + 模型，聚合前）")
    if not issues:
        lines.append("- （无）")
    for issue in issues:
        cat = getattr(issue, "category", 0)
        lines.append(f"- **[{issue.degree}]** [{issue.title}]（category={cat}）: {issue.comment}")
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
