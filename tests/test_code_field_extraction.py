from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.code_field_extraction import extract_fields_from_tasks


def test_single_keyword_extraction() -> None:
    tasks = [
        {
            "字段集": "甲方：合同主体（甲方）",
            "取值来源": "1##text##北京甲公司\n2##text##乙方：上海乙公司",
        }
    ]
    out = extract_fields_from_tasks(tasks)
    assert len(out) == 1
    assert out[0]["review_target_field"] == "甲方"
    assert "北京甲公司" in out[0]["review_target_content"]


def test_range_extraction_in_bounds() -> None:
    tasks = [
        {
            "字段集": "金额：合同金额取值范围【10，20】",
            "取值来源": "3##number##15万元",
        }
    ]
    out = extract_fields_from_tasks(tasks)
    assert out[0]["review_target_field"] == "金额"
    assert "15" in out[0]["review_target_content"]


def test_range_extraction_out_of_bounds_empty() -> None:
    tasks = [
        {
            "字段集": "金额：合同金额取值范围【10，20】",
            "取值来源": "3##number##99万元",
        }
    ]
    out = extract_fields_from_tasks(tasks)
    assert out[0]["review_target_content"] == ""
