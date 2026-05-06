from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List

from contract_review_api.core.models import FieldCandidate, Paragraph


FIELD_PATTERNS: Dict[str, List[str]] = {
    "project_name": [r"项目名称[:：]\s*(.+)", r"合作协议[\(（]?.*?[\)）]?"],
    "contract_type": [r"合同类型[:：]\s*(.+)", r"保险项目合作协议"],
    "party_info": [r"甲方[:：]\s*(.+)", r"乙方[:：]\s*(.+)", r"丙方[:：]\s*(.+)"],
    "effective_period": [r"自\s*\d{4}年\d{1,2}月\d{1,2}日.*?至\s*\d{4}年\d{1,2}月\d{1,2}日"],
    "contact_address": [r"地址[:：]\s*(.+)"],
}


def extract_field_candidates(paragraphs: Iterable[Paragraph]) -> List[FieldCandidate]:
    collected: Dict[str, List[FieldCandidate]] = defaultdict(list)
    for para in paragraphs:
        for field_key, patterns in FIELD_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, para.text):
                    value = match.group(1).strip() if match.groups() else match.group(0).strip()
                    if not value:
                        continue
                    collected[field_key].append(
                        FieldCandidate(
                            field_key=field_key,
                            value=value,
                            confidence=0.75,
                            evidence_paragraphs=[para.paragraph_no],
                        )
                    )
    merged: List[FieldCandidate] = []
    for field_key, items in collected.items():
        merged.append(_pick_best(field_key, items))
    return merged


def _pick_best(field_key: str, items: List[FieldCandidate]) -> FieldCandidate:
    # Prefer more informative values and aggregate evidence pointers.
    best = sorted(items, key=lambda i: (len(i.value), i.confidence), reverse=True)[0]
    evidence = sorted({p for item in items for p in item.evidence_paragraphs})
    best.evidence_paragraphs = evidence
    best.field_key = field_key
    return best
