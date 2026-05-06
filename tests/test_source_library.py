from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.source_library import (
    assemble_source_inputs,
    build_source_library,
    format_source_library_for_llm,
)


def test_build_source_library_all_nonempty() -> None:
    lib = build_source_library("subj", "main", "ann", "biz")
    assert len(lib) == 4
    assert [x["src"] for x in lib] == [1, 2, 3, 4]
    assert lib[0]["content"] == "subj"
    assert lib[3]["content"] == "biz"


def test_build_source_library_preserves_empty_slots() -> None:
    lib = build_source_library("", "only_main", "", "")
    assert lib[0]["content"] == ""
    assert lib[1]["content"] == "only_main"
    assert lib[2]["content"] == ""
    assert lib[3]["content"] == ""


def test_build_source_library_all_empty_still_four() -> None:
    lib = build_source_library("", "", "", "")
    assert len(lib) == 4
    assert all(x["content"] == "" for x in lib)


def test_format_source_library_for_llm_labels_src() -> None:
    lib = build_source_library("a", "b", "", "d")
    s = format_source_library_for_llm(lib)
    assert "[src=1]" in s and "a" in s
    assert "[src=4]" in s and "d" in s


def test_assemble_source_inputs_main_and_annexes(tmp_path: Path) -> None:
    main = tmp_path / "m.txt"
    main.write_text("FILE_MAIN", encoding="utf-8")
    att = tmp_path / "a.txt"
    att.write_text("FILE_ATT", encoding="utf-8")
    subj, main_c, ann, biz = assemble_source_inputs(
        "INLINE",
        ["REMOTE_ATT"],
        [main, att],
    )
    assert subj == ""
    assert "INLINE" in main_c and "FILE_MAIN" in main_c
    assert "REMOTE_ATT" in ann and "FILE_ATT" in ann
    assert biz == ""
