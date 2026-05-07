from __future__ import annotations

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
