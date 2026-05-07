from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.field_extraction_tasks import build_field_extraction_task_split


def test_split_mode_1_vs_23() -> None:
    pending = [
        {"name": "a", "mode": 1, "src": 1},
        {"name": "b", "mode": 23, "src": 1},
        {"name": "c", "mode": 2, "src": 1},
        {"name": "d", "mode": 3, "src": 2},
    ]
    out = build_field_extraction_task_split(pending)
    assert [x["name"] for x in out["mode_1"]] == ["a"]
    assert {x["name"] for x in out["mode_23"]} == {"b", "c", "d"}


def test_unknown_mode_defaults_to_mode_1() -> None:
    out = build_field_extraction_task_split([{"name": "x", "mode": 99, "src": 1}])
    assert [x["name"] for x in out["mode_1"]] == ["x"]
