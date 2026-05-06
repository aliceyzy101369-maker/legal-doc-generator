from __future__ import annotations

import re
from typing import Any, List

from contract_review_api.api.schemas import ExtractedInfoItem, FinalCommentItem, FinalOutput
from contract_review_api.core.models import FieldCandidate, ReviewIssue


def build_final_output(fields: List[FieldCandidate], issues: List[ReviewIssue]) -> FinalOutput:
    comment_list: List[FinalCommentItem] = []
    extracted_info: List[ExtractedInfoItem] = []

    for issue in issues:
        category = _normalize_category(issue.category)
        item: dict[str, Any] = {
            "title": issue.title,
            "comment": issue.comment,
            "degree": issue.degree or "中",
            "category": category,
        }
        if category == 1:
            change_type = _normalize_change_type(issue.change_type)
            item["change_type"] = change_type
            item["original_id"] = _normalize_original_id(issue.evidence, change_type)
            item["revised_text"] = _clean_revised_text(issue.revised_text or "")
        comment_list.append(FinalCommentItem(**item))

    for field in fields:
        extracted_info.append(ExtractedInfoItem(title=field.field_key, comment=_clean_revised_text(field.value)))

    return FinalOutput(comment_list=comment_list, extracted_info=extracted_info)


def normalize_review_issues(raw_issues: List[Any]) -> List[dict[str, Any]]:
    """
    Normalize LLM/parsed review issues into strict key shapes:
    - category=0: keep {title, comment, degree, category} only
    - category=1: keep {title, comment, degree, category, change_type, original_id, revised_text}
    """
    out: List[dict[str, Any]] = []

    for raw in raw_issues:
        issue: dict[str, Any] | None
        if isinstance(raw, ReviewIssue):
            issue = {
                "title": raw.title,
                "comment": raw.comment,
                "degree": raw.degree,
                "category": raw.category,
                "change_type": raw.change_type,
                # In our pipeline, evidence is used as the "original_id" list.
                "evidence": raw.evidence,
                "revised_text": raw.revised_text,
            }
        elif isinstance(raw, dict):
            issue = raw
        else:
            continue

        title = str(issue.get("title", "")).strip()
        comment = str(issue.get("comment", "")).strip()
        degree = str(issue.get("degree", "中")).strip() or "中"
        category = _normalize_category(issue.get("category", 0))

        if category == 1:
            change_type = _normalize_change_type(issue.get("change_type"))

            original_id_src = issue.get("original_id", issue.get("evidence"))
            original_id_evidence = original_id_src if isinstance(original_id_src, list) else None
            original_id = _normalize_original_id(original_id_evidence, change_type)

            revised_text = _clean_revised_text(issue.get("revised_text") or "")
            out.append(
                {
                    "title": title,
                    "comment": comment,
                    "degree": degree,
                    "category": 1,
                    "change_type": change_type,
                    "original_id": original_id,
                    "revised_text": revised_text,
                }
            )
        else:
            out.append({"title": title, "comment": comment, "degree": degree, "category": 0})

    return out


def _clean_revised_text(text: str) -> str:
    cleaned = re.sub(r"[*_]+", "", str(text or ""))
    cleaned = re.sub(r"\d+##[A-Za-z]+##", "", cleaned)
    return cleaned.strip()


def _normalize_category(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return 1 if n == 1 else 0


def _normalize_original_id(evidence: List[int] | None, change_type: str) -> List[int]:
    if change_type == "新增":
        return [1]
    if not evidence:
        return [1]
    ids: List[int] = []
    for item in evidence:
        try:
            val = int(item)
        except (TypeError, ValueError):
            continue
        ids.append(val)
    return ids or [1]


def _normalize_change_type(value: Any) -> str:
    allowed = {"修订", "删除", "新增"}
    if isinstance(value, str) and value in allowed:
        return value
    return "新增"

