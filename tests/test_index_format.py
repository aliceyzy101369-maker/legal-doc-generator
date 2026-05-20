from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.index_format import filter_empty_marker_map, format_index_ranges


def test_format_index_ranges() -> None:
    assert format_index_ranges([1, 3, 4, 5, 10, 47]) == "1,3-5,10,47"


def test_filter_empty_marker_map() -> None:
    m = {"a": [1, 2], "b": [], "c": "", "d": [3]}
    assert filter_empty_marker_map(m) == {"a": [1, 2], "d": [3]}
