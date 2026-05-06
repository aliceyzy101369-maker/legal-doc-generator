from __future__ import annotations

import json
import re
from typing import Any


def remove_think_prefix(text: str) -> str:
    """Remove leading model "thinking" section if present."""
    current = str(text or "")
    marker = "</think>"
    idx = current.find(marker)
    if idx != -1:
        current = current[idx + len(marker) :]
    return current.strip()


def remove_markdown_fence(text: str) -> str:
    """Remove markdown code fences (``` and ```xxx) lines."""
    current = str(text or "")
    current = re.sub(r"^\s*```[\w-]*\s*$", "", current, flags=re.MULTILINE)
    current = re.sub(r"^\s*```\s*$", "", current, flags=re.MULTILINE)
    return current.strip()


def parse_json_tolerant(text: Any) -> dict | list:
    """
    Best-effort JSON parsing:
    - Empty input -> {}
    - If json.loads works -> return parsed value
    - Otherwise try extracting `"key": [...]` pairs from broken output
    """
    current = str(text or "")
    if not current.strip():
        return {}

    try:
        parsed = json.loads(current)
    except Exception:
        # Regex fallback: extract `"key": [ ... ]`-shaped dict entries.
        # This intentionally assumes the value part is a single JSON array.
        pairs: dict[str, list] = {}
        pattern = re.compile(
            r"(?P<q>\"|')(?P<key>.+?)(?P=q)\s*:\s*(?P<value>\[[\s\S]*?\])",
            flags=re.MULTILINE,
        )
        for m in pattern.finditer(current):
            key = m.group("key")
            value_str = m.group("value")
            try:
                value = json.loads(value_str)
            except Exception:
                continue
            if isinstance(value, list):
                pairs[str(key)] = value
        return pairs if pairs else {}

    # Filter dict outputs to keep only keys that map to lists.
    if isinstance(parsed, dict):
        out: dict[str, list] = {}
        for k, v in parsed.items():
            if isinstance(k, str) and isinstance(v, list):
                out[k] = v
        return out
    return parsed


def clean_llm_output(raw_text: str) -> dict | list:
    """Main cleaning entry for all LLM outputs."""
    step1 = remove_think_prefix(raw_text)
    step2 = remove_markdown_fence(step1)
    return parse_json_tolerant(step2)


def parse_json_object_tolerant(text: Any) -> dict[str, Any]:
    """
    Parse a JSON object for field-extraction style outputs (string or nested dict values).
    Invalid or non-object JSON returns {}.
    """
    current = str(text or "")
    if not current.strip():
        return {}
    try:
        parsed = json.loads(current)
    except Exception:
        return {}
    if isinstance(parsed, dict):
        out: dict[str, Any] = {}
        for k, v in parsed.items():
            if k is None:
                continue
            out[str(k)] = v
        return out
    return {}


def clean_llm_field_json(raw_text: str) -> dict[str, Any]:
    """Strip think/fences then parse a single JSON object of field extractions."""
    step1 = remove_think_prefix(raw_text)
    step2 = remove_markdown_fence(step1)
    return parse_json_object_tolerant(step2)

