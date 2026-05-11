import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.core.models import Paragraph
from contract_review_api.services.markdown_line_parser import (
    is_dify_markdown_line_document,
    is_numberish_line_category,
    is_paragraph_eligible_category,
    parse_markdown_lines,
    paragraphs_from_markdown_lines,
)


def test_parse_standard_lines():
    text = """1##基本信息##甲方：北京甲公司
2##付款条款##付款方式：双方另行协商
not a valid line
3##杂项##备注
"""
    rows = parse_markdown_lines(text)
    assert len(rows) == 3
    assert rows[0].pid == 1 and rows[0].text.startswith("甲方")
    assert rows[1].category == "付款条款"


def test_mixed_with_plain_text_not_enough_for_mode():
    text = """普通段落一行
1##a##b
2##c##d
"""
    assert is_dify_markdown_line_document(text) is True


def test_invalid_lines_filtered():
    assert parse_markdown_lines("### not valid\nno pid here") == []


def test_duplicate_pid_merged():
    text = "1##a##first\n1##a##second"
    rows = parse_markdown_lines(text)
    assert len(rows) == 1
    assert "first" in rows[0].text and "second" in rows[0].text


def test_empty_body_keeps_pid():
    text = "5##cat##"
    rows = parse_markdown_lines(text)
    assert rows[0].pid == 5
    assert rows[0].text == ""


def test_paragraphs_from_lines_number_category():
    paras = paragraphs_from_markdown_lines("rid", "1##number##hello\n2##number##world")
    assert isinstance(paras[0], Paragraph)
    assert paras[0].paragraph_no == 1
    assert paras[0].text == "hello"


def test_paragraphs_from_lines_nuber_typo_branch():
    paras = paragraphs_from_markdown_lines("rid", "10##nuber##附件一行")
    assert len(paras) == 1
    assert paras[0].text == "附件一行"


def test_paragraphs_exclude_non_numberish_categories():
    paras = paragraphs_from_markdown_lines(
        "rid",
        "1##基本信息##skip\n2##number##keep",
    )
    assert len(paras) == 1
    assert paras[0].text == "keep"


def test_numberish_category_case_insensitive():
    assert is_numberish_line_category("Number") is True
    assert is_numberish_line_category("NUBER") is True


def test_paragraph_allowlist_extends_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKDOWN_PARAGRAPH_CATEGORY_ALLOWLIST", "基本信息,付款条款")
    assert is_paragraph_eligible_category("基本信息") is True
    assert is_paragraph_eligible_category("付款条款") is True
    assert is_paragraph_eligible_category("other") is False
    paras = paragraphs_from_markdown_lines(
        "rid",
        "1##基本信息##from allow\n2##number##numline",
    )
    assert len(paras) == 2
    assert paras[0].text == "from allow"
    assert paras[1].text == "numline"
