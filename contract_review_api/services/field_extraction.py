from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Set

from contract_review_api.core.models import FieldCandidate, Paragraph
from contract_review_api.services.llm_engine import run_llm_field_extraction


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


def _field_refine_mode() -> str:
    flag = str(os.getenv("LLM_FIELD_REFINE", "") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return "llm"
    raw = str(os.getenv("FIELD_REFINE_MODE", "regex") or "regex").strip().lower()
    if raw in ("llm", "mode_23", "mode23"):
        return "llm"
    # regex / rules / default: coarse + rules gap-fill only (no field LLM)
    return "rules"


def collect_target_field_names(rules: List[dict]) -> Set[str]:
    names: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        for tf in rule.get("target_fields", []):
            if isinstance(tf, dict) and tf.get("name"):
                n = str(tf["name"]).strip()
                if n:
                    names.add(n)
    return names


def _merge_coarse_llm_rules_gapfill(
    coarse: List[FieldCandidate],
    llm_map: dict[str, dict[str, Any]],
    rules_names: Set[str],
    *,
    contract_type_override: str | None,
) -> List[FieldCandidate]:
    """Coarse merge first; non-empty LLM values override per field; then rules gap-fill; then contract_type."""
    from contract_review_api.services.result_merge import merge_fields

    coarse_merged = merge_fields(coarse, contract_type_override=None)
    by_key: dict[str, FieldCandidate] = {f.field_key: f for f in coarse_merged}
    key_order: list[str] = [f.field_key for f in coarse_merged]
    seen_order = set(key_order)

    for key, spec in llm_map.items():
        val = str(spec.get("value", "") or "").strip()
        if not val:
            continue
        ev_list = spec.get("evidence_paragraphs") or []
        evidence: list[int] = []
        for x in ev_list:
            try:
                evidence.append(int(x))
            except (TypeError, ValueError):
                continue
        evidence = sorted(set(evidence))
        try:
            conf = float(spec.get("confidence", 0.85))
        except (TypeError, ValueError):
            conf = 0.85
        conf = min(max(conf, 0.0), 1.0)
        prev = by_key.get(key)
        base_conf = prev.confidence if prev else 0.0
        prev_val = str(prev.value or "").strip() if prev else ""
        if prev_val:
            merged_val = f"{prev_val}\n{val}"
            evidence = sorted(set((prev.evidence_paragraphs if prev else []) + evidence))
        else:
            merged_val = val
        by_key[key] = FieldCandidate(
            field_key=key,
            value=merged_val,
            confidence=max(conf, base_conf),
            evidence_paragraphs=evidence,
        )
        if key not in seen_order:
            key_order.append(key)
            seen_order.add(key)

    for name in sorted(rules_names):
        if name not in by_key:
            by_key[name] = FieldCandidate(field_key=name, value="", confidence=0.25, evidence_paragraphs=[])
        if name not in seen_order:
            key_order.append(name)
            seen_order.add(name)

    for k in by_key:
        if k not in seen_order:
            key_order.append(k)
            seen_order.add(k)

    ordered = [by_key[k] for k in key_order if k in by_key]
    return merge_fields(ordered, contract_type_override=contract_type_override)


def refine_field_candidates(
    coarse: List[FieldCandidate],
    rules: List[dict],
    *,
    contract_type_override: str | None = None,
    contract_text: str | None = None,
    source_library: list[dict] | None = None,
) -> tuple[List[FieldCandidate], List[str]]:
    """
    Mode-23 style: merge + gap-fill target_fields from rules + optional contract_type override.

    FIELD_REFINE_MODE=llm: run LLM extraction on source_library / contract_text; non-empty LLM values
    are merged with coarse per field using \\n. Long texts use chunked extraction in llm_engine (real mode).
    rules target_fields still gap-filled.

    Returns (refined_fields, warnings).
    """
    from contract_review_api.services.result_merge import merge_fields

    warnings: list[str] = []
    if not coarse:
        warnings.append("coarse_field_extraction_empty")

    names = collect_target_field_names(rules)
    standard_keys = set(FIELD_PATTERNS.keys())
    field_name_union = sorted(names | standard_keys)

    extraction_text: str | None = None
    if source_library:
        from contract_review_api.services.source_library import format_source_library_for_llm

        extraction_text = format_source_library_for_llm(source_library)
    elif contract_text is not None and str(contract_text).strip():
        extraction_text = str(contract_text).strip()

    if _field_refine_mode() == "llm" and extraction_text:
        llm_map, llm_warnings = run_llm_field_extraction(extraction_text, field_name_union)
        warnings.extend(llm_warnings)
        merged = _merge_coarse_llm_rules_gapfill(
            coarse,
            llm_map,
            names,
            contract_type_override=contract_type_override,
        )
        return merged, warnings

    merged = merge_fields(coarse, contract_type_override=contract_type_override)

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
