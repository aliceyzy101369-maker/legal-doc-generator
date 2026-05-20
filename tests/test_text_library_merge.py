from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.text_library_merge import merge_review_text_libraries


def test_merge_concatenates_same_field() -> None:
    llm = [{"review_target_field": "甲方", "review_target_content": "粗提"}]
    code = [{"review_target_field": "甲方", "review_target_content": "代码"}]
    out = merge_review_text_libraries(llm, code)
    assert out[0]["review_target_content"] == "粗提\n代码"
