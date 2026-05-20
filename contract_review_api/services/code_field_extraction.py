from __future__ import annotations

import re
from typing import Any

_LINE_RE = re.compile(r"^(\d+)##([^#]*?)##(.*)$")
_PAREN_TERMS_RE = re.compile(r"（([^）]+)）")
_RANGE_RE = re.compile(r"取值范围【([^】]+)】")
_SUMMARY_HINTS = ("总结", "提炼")


def _parse_field_blocks(字段集: str) -> list[tuple[str, str]]:
    blocks = re.split(r"\n\s*\n", str(字段集 or "").strip())
    out: list[tuple[str, str]] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        sep = "：" if "：" in block else (":" if ":" in block else None)
        if sep is None:
            out.append((block, block))
            continue
        name, desc = block.split(sep, 1)
        out.append((name.strip(), desc.strip()))
    return out


def _parse_source_lines(source: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for raw in str(source or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if m:
            out.append((int(m.group(1)), str(m.group(2) or "").strip(), str(m.group(3) or "").strip()))
        else:
            out.append((len(out) + 1, "text", line))
    return out


def _terms_from_desc(desc: str) -> list[str]:
    terms: list[str] = []
    for m in _PAREN_TERMS_RE.finditer(desc):
        inner = str(m.group(1) or "").strip()
        for part in re.split(r"[,，、]", inner):
            p = part.strip()
            if p:
                terms.append(p)
    return terms


def _parse_range_bounds(desc: str) -> tuple[float, float] | None:
    m = _RANGE_RE.search(desc)
    if not m:
        return None
    parts = re.split(r"[,，]", str(m.group(1) or ""))
    if len(parts) < 2:
        return None
    try:
        lo = float(str(parts[0]).strip())
        hi = float(str(parts[1]).strip())
    except ValueError:
        return None
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def _first_number_in_text(text: str) -> float | None:
    m = re.search(r"[\d.]+", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _is_summary_desc(desc: str) -> bool:
    return any(h in desc for h in _SUMMARY_HINTS)


def _summarize_content(parts: list[str], limit: int = 300) -> str:
    joined = "；".join(p for p in parts if p)
    if len(joined) <= limit:
        return joined
    return joined[:limit]


def _extract_one_field(name: str, desc: str, source_lines: list[tuple[int, str, str]]) -> str:
    bounds = _parse_range_bounds(desc)
    if bounds is not None:
        lo, hi = bounds
        for _pid, _cat, content in source_lines:
            val = _first_number_in_text(content)
            if val is not None and lo <= val <= hi:
                return content
        return ""

    terms = _terms_from_desc(desc)
    if not terms and name:
        terms = [name]

    matched_lines: list[str] = []
    for pid, cat, content in source_lines:
        if not content:
            continue
        hit = any(t in content or t in name for t in terms)
        if hit:
            matched_lines.append(f"{pid}##{cat}##{content}")

    if _is_summary_desc(desc):
        bodies = [c for _p, _c, c in source_lines if c]
        if matched_lines:
            bodies = [ln.split("##", 2)[-1] if "##" in ln else ln for ln in matched_lines]
        return _summarize_content(bodies)

    return "\n".join(matched_lines)


def extract_fields_from_tasks(tasks: list[dict]) -> list[dict]:
    """
  v1.4 mode_0 code extraction.

  Input tasks: [{"字段集": "...", "取值来源": "..."}]
  Output: [{"review_target_field", "review_target_content"}]
    """
    out: list[dict[str, Any]] = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        field_set = str(task.get("字段集", "") or "")
        source = str(task.get("取值来源", "") or "")
        source_lines = _parse_source_lines(source)
        for name, desc in _parse_field_blocks(field_set):
            content = _extract_one_field(name, desc, source_lines)
            out.append({"review_target_field": name, "review_target_content": content or ""})
    return out
