from __future__ import annotations

import re
from typing import Dict, Iterable, List

from contract_review_api.core.models import FieldCandidate, Paragraph


FIELD_PATTERNS: Dict[str, List[str]] = {
    "project_name": [r"项目名称[:：]\s*(.+)", r"合作协议[\(（]?.*?[\)）]?"],
    "contract_type": [r"合同类型[:：]\s*(.+)", r"保险项目合作协议"],
    "party_info": [r"甲方[:：]\s*(.+)", r"乙方[:：]\s*(.+)", r"丙方[:：]\s*(.+)"],
    "effective_period": [r"自\s*\d{4}年\d{1,2}月\d{1,2}日.*?至\s*\d{4}年\d{1,2}月\d{1,2}日"],
    "contact_address": [r"地址[:：]\s*(.+)"],
}


def extract_field_candidates_coarse(paragraphs: Iterable[Paragraph]) -> List[FieldCandidate]:
    """Mode-1 style: collect every regex hit (may contain duplicate field_key)."""
    out: List[FieldCandidate] = []
    for para in paragraphs:
        for field_key, patterns in FIELD_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, para.text):
                    value = match.group(1).strip() if match.groups() else match.group(0).strip()
                    if not value:
                        continue
                    out.append(
                        FieldCandidate(
                            field_key=field_key,
                            value=value,
                            confidence=0.65,
                            evidence_paragraphs=[para.paragraph_no],
                        )
                    )
    return out


def refine_field_candidates(
    coarse: List[FieldCandidate],
    rules: List[dict],
    *,
    contract_type_override: str | None = None,
) -> tuple[List[FieldCandidate], List[str]]:
    """
    Mode-23 style: merge + gap-fill target_fields from rules + optional contract_type override.
    Returns (refined_fields, warnings).
    """
    from contract_review_api.services.result_merge import merge_fields

    warnings: list[str] = []
    if not coarse:
        warnings.append("coarse_field_extraction_empty")

    merged = merge_fields(coarse, contract_type_override=contract_type_override)

    names: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        for tf in rule.get("target_fields", []):
            if isinstance(tf, dict) and tf.get("name"):
                names.add(str(tf["name"]).strip())

    existing = {f.field_key for f in merged}
    for name in sorted(names):
        if name and name not in existing:
            merged.append(FieldCandidate(field_key=name, value="", confidence=0.25, evidence_paragraphs=[]))

    return merged, warnings


def extract_field_candidates(paragraphs: Iterable[Paragraph]) -> List[FieldCandidate]:
    """Backward-compatible single-shot extraction (coarse + refine with no rule gap-fill)."""
    coarse = extract_field_candidates_coarse(paragraphs)
    refined, _warnings = refine_field_candidates(coarse, [], contract_type_override=None)
    return refined
