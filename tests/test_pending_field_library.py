from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.pending_field_library import build_pending_object_field_library


def test_filters_src_zero_only() -> None:
    rules = [
        {
            "title": "r1",
            "target_fields": [
                {"name": "keep_me", "src": 1, "mode": 1, "desc": "a"},
                {"name": "anchor", "src": 0, "mode": 1, "desc": "anchor desc"},
                {"name": "code_mode", "src": 1, "mode": 0, "desc": "static via code"},
                {"name": "keep_two", "src": 2, "mode": 23, "desc": "b"},
            ],
        }
    ]
    lib = build_pending_object_field_library(rules)
    names = [x["name"] for x in lib]
    assert names == ["keep_me", "code_mode", "keep_two"]


def test_mode_zero_included_when_src_not_zero() -> None:
    rules = [
        {
            "title": "r1",
            "target_fields": [{"name": "m0", "src": 2, "mode": 0, "desc": "（关键词）"}],
        }
    ]
    lib = build_pending_object_field_library(rules)
    assert len(lib) == 1
    assert lib[0]["mode"] == 0


def test_dedupes_by_name_first_wins() -> None:
    rules = [
        {"title": "a", "target_fields": [{"name": "x", "src": 1, "mode": 1, "desc": "first"}]},
        {"title": "b", "target_fields": [{"name": "x", "src": 2, "mode": 1, "desc": "second"}]},
    ]
    lib = build_pending_object_field_library(rules)
    assert len(lib) == 1
    assert lib[0]["rule_title"] == "a"
    assert lib[0]["desc"] == "first"


def test_skips_non_dict_and_empty_name() -> None:
    rules = [
        {
            "title": "z",
            "target_fields": [
                "bad",
                {"name": "", "src": 1, "mode": 1},
                {"name": "ok", "src": 1, "mode": 1},
            ],
        }
    ]
    lib = build_pending_object_field_library(rules)
    assert [x["name"] for x in lib] == ["ok"]
