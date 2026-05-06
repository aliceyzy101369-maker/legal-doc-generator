import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services import llm_cleaner


def test_remove_think_prefix_truncates_after_marker():
    raw = "一些前置内容</think> {\"a\": 1}"
    assert llm_cleaner.remove_think_prefix(raw) == "{\"a\": 1}"


def test_remove_markdown_fence_removes_triple_backticks_lines():
    raw = "```json\n[1,2]\n```"
    assert llm_cleaner.remove_markdown_fence(raw) == "[1,2]"


def test_parse_json_tolerant_empty_returns_dict():
    assert llm_cleaner.parse_json_tolerant("") == {}
    assert llm_cleaner.parse_json_tolerant(None) == {}


def test_parse_json_tolerant_extracts_key_list_pairs_when_json_invalid():
    # Intentionally invalid JSON envelope (missing trailing `}`)
    raw = '{ "issues": [ {"title":"t","comment":"c","degree":"高","category":0} ]'
    out = llm_cleaner.parse_json_tolerant(raw)
    assert isinstance(out, dict)
    assert "issues" in out
    assert isinstance(out["issues"], list)
    assert len(out["issues"]) == 1
    assert out["issues"][0]["title"] == "t"


def test_clean_llm_output_chains_all_steps():
    raw = """
    </think>
    ```json
    [{\"title\":\"t\",\"comment\":\"c\",\"degree\":\"高\",\"category\":0}]
    ```
    """
    out = llm_cleaner.clean_llm_output(raw)
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["title"] == "t"

