from __future__ import annotations

from typing import Any


def merge_review_text_libraries(llm_fields: list, code_fields: list) -> list[dict[str, Any]]:
    """
    构建待审文本库2 (v1.4): merge LLM/refined fields with code extraction results.

    Each row: review_target_field, review_target_content.
    Same field key: concatenate non-empty contents with \\n.
    """
    buckets: dict[str, list[str]] = {}
    order: list[str] = []

    def _ingest(rows: list) -> None:
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("review_target_field", "") or "").strip()
            if not key:
                continue
            val = str(row.get("review_target_content", "") or "").strip()
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            if val:
                buckets[key].append(val)

    _ingest(llm_fields)
    _ingest(code_fields)

    return [
        {
            "review_target_field": key,
            "review_target_content": "\n".join(buckets[key]),
        }
        for key in order
    ]
