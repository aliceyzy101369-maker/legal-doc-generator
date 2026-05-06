import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.text_processing import chunk_tasks


def test_chunk_tasks_json_list_string_splits_by_elements():
    tasks = [
        {
            "取值来源": '["aaaa","bbbb","cccc"]',
            "meta": "m1",
        }
    ]
    out = chunk_tasks(tasks, limit=9)
    assert len(out) == 2
    assert out[0]["meta"] == "m1"
    assert out[0]["取值来源"] == "aaaa\nbbbb"
    assert out[1]["取值来源"] == "cccc"


def test_chunk_tasks_markdown_splits_by_top_level_heading_and_respects_limit():
    src = "# A\n" + ("x" * 10) + "\n# B\n" + ("y" * 10)
    tasks = [{"待审文本": src, "meta": "m2"}]
    out = chunk_tasks(tasks, limit=15)
    assert len(out) >= 1
    # Each chunk should not exceed the limit (roughly measured by final string length).
    assert all(len(t["待审文本"]) <= 15 for t in out)
    assert all(t["meta"] == "m2" for t in out)

