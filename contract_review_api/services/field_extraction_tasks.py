from __future__ import annotations

import os
from typing import Any, List


def build_field_extraction_task_split(pending_object_field_library: List[dict[str, Any]]) -> dict[str, List[dict[str, Any]]]:
    """
    Dify workflow §5.1「构建字段提取任务」: split pending field rows into coarse (mode_1) vs refine (mode_23).

    Classification (aligned with common ruleset usage):
    - mode == 1 -> mode_1 (粗提 / 段落定位语义)
    - mode in {2, 3, 23} -> mode_23 (精提+判断)
    - missing or other numeric modes -> mode_1 (backward compatible with rulesets that only set mode=1)
    """
    mode_1: list[dict[str, Any]] = []
    mode_23: list[dict[str, Any]] = []
    for row in pending_object_field_library or []:
        if not isinstance(row, dict):
            continue
        m = row.get("mode")
        try:
            mi = int(m) if m is not None and str(m).strip() != "" else 1
        except (TypeError, ValueError):
            mi = 1
        item = dict(row)
        if mi == 1:
            mode_1.append(item)
        elif mi in (2, 3, 23):
            mode_23.append(item)
        else:
            mode_1.append(item)
    return {"mode_1": mode_1, "mode_23": mode_23}


def _source_library_to_map(source_library: List[dict[str, Any]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in source_library or []:
        if not isinstance(item, dict):
            continue
        try:
            src = int(item.get("src", 0))
        except (TypeError, ValueError):
            continue
        out[src] = str(item.get("content", "") or "")
    return out


def _field_task_source_preview_limit() -> int:
    raw = os.getenv("FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS", "6000") or "6000"
    try:
        return max(0, min(int(raw), 100_000))
    except ValueError:
        return 6000


def enrich_field_extraction_tasks_with_sources(
    field_extraction_tasks: dict[str, List[dict[str, Any]]],
    source_library: List[dict[str, Any]],
) -> dict[str, List[dict[str, Any]]]:
    """
    Dify §5.1: attach src→content mapping per task row (dry-run observability).

    Adds: source_matched_src, source_full_len, source_preview (truncated), source_preview_truncated.
    preview length from FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS (0 = omit preview text).
    """
    src_map = _source_library_to_map(source_library)
    limit = _field_task_source_preview_limit()
    result: dict[str, list[dict[str, Any]]] = {"mode_1": [], "mode_23": []}
    for bucket in ("mode_1", "mode_23"):
        for row in field_extraction_tasks.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            r = dict(row)
            sk = r.get("src")
            try:
                src_i = int(sk) if sk is not None and str(sk).strip() != "" else 1
            except (TypeError, ValueError):
                src_i = 1
            full = src_map.get(src_i, "")
            r["source_matched_src"] = src_i
            r["source_full_len"] = len(full)
            if limit <= 0:
                r["source_preview"] = ""
                r["source_preview_truncated"] = len(full) > 0
            else:
                r["source_preview"] = full[:limit]
                r["source_preview_truncated"] = len(full) > limit
            result[bucket].append(r)
    return result
