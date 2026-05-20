from __future__ import annotations

from typing import Any, List


def build_pending_object_field_library(rules: List[dict]) -> List[dict[str, Any]]:
    """
    Dify node 4.4「构建待审对象字段库」:
    - Walk all rules' target_fields
    - Drop non-dict entries, empty name, anchor/static fields (src == 0 only; v1.4 keeps mode==0)
    - Dedupe by name (first occurrence wins)
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        for tf in rule.get("target_fields", []) or []:
            if not isinstance(tf, dict):
                continue
            name = str(tf.get("name", "") or "").strip()
            if not name:
                continue
            src = tf.get("src", None)
            try:
                src_i = int(src) if src is not None and str(src).strip() != "" else None
            except (TypeError, ValueError):
                src_i = None
            if src_i == 0:
                continue
            if name in seen:
                continue
            seen.add(name)
            mode = tf.get("mode", None)
            try:
                mode_i = int(mode) if mode is not None and str(mode).strip() != "" else None
            except (TypeError, ValueError):
                mode_i = None
            row: dict[str, Any] = {
                "name": name,
                "src": src_i if src_i is not None else src,
                "mode": mode_i if mode_i is not None else mode,
            }
            if "desc" in tf:
                row["desc"] = tf.get("desc")
            if "title" in rule:
                row["rule_title"] = rule.get("title")
            out.append(row)
    return out
