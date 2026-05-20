from __future__ import annotations

from typing import Any


def format_index_ranges(indices: list[int]) -> str:
    """Format paragraph indices as compact ranges, e.g. [1,3,4,5,10,47] -> \"1,3-5,10,47\"."""
    if not indices:
        return ""
    nums = sorted({int(i) for i in indices})
    parts: list[str] = []
    start = end = nums[0]
    for n in nums[1:]:
        if n == end + 1:
            end = n
            continue
        parts.append(str(start) if start == end else f"{start}-{end}")
        start = end = n
    parts.append(str(start) if start == end else f"{start}-{end}")
    return ",".join(parts)


def filter_empty_marker_map(marker_map: dict[str, Any]) -> dict[str, Any]:
    """Drop marker-map entries with empty or missing index lists (v1.4 coarse output hygiene)."""
    out: dict[str, Any] = {}
    for key, val in (marker_map or {}).items():
        k = str(key or "").strip()
        if not k:
            continue
        if val is None:
            continue
        if isinstance(val, list):
            if not val:
                continue
            if all(not str(x).strip() for x in val):
                continue
        elif isinstance(val, str) and not val.strip():
            continue
        out[k] = val
    return out
