# 第十八阶段：三合一版 v1.4 对齐

## 要点

| 项 | 实现 |
|----|------|
| §4.4 待审字段库 | `pending_field_library` 仅过滤 `src==0`（保留 `mode==0`） |
| §5.1 任务拆分 | `mode_0` / `mode_1` / `mode_23` |
| mode_0 代码提取 | `code_field_extraction.extract_fields_from_tasks` |
| 待审文本库2 合流 | `text_library_merge.merge_review_text_libraries`（同字段 `\n` 拼接） |
| 主链 | `pipeline._apply_mode0_text_library_merge`（精提/粗提后） |
| 字段任务切片 | `field_extraction_chunking.split_field_extraction_items` + env 限额/重叠 |
| 精提 prompt v1.4 | `prompts/field_refine_v14.txt` → `llm_engine._field_refine_system_prompt` |
| 粗提段落编号 | `index_format.format_index_ranges`；`filter_empty_marker_map` 去空字段 |

## 测试

- `tests/test_pending_field_library.py`
- `tests/test_field_extraction_tasks.py`
- `tests/test_code_field_extraction.py`
- `tests/test_field_extraction_chunking.py`
- `tests/test_text_library_merge.py`
- `tests/test_index_format.py`
