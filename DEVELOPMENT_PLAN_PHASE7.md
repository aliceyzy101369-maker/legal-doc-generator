# 第七阶段：精提 LLM 分段（8k 级）

## 交付

1. **`run_llm_field_extraction`**（`LLM_MODE=real`）  
   - 在 `FIELD_REFINE_USE_CHUNKS=true`（默认）且正文长度 **大于** `FIELD_REFINE_CHUNK_SIZE`（默认 **8000**）时，按固定字符窗口切段，**顺序**调用 `_run_llm_field_extraction_one`，再用 `_merge_llm_field_map_parts` 合并。  
   - `FIELD_REFINE_MAX_CHUNKS`（默认 **64**，上限 256）防止超长合同刷爆调用次数；超出部分丢弃并警告 `llm_field_refine_chunk_cap_truncated`。  
   - 多段时警告 `llm_field_refine_chunked:<n>`。  
   - `FIELD_REFINE_USE_CHUNKS=false` 时恢复「单请求 + `FIELD_REFINE_TEXT_LIMIT` 截断」行为。  

2. **合并语义**  
   - 同字段多段非空 `value` 用 `\n` 拼接；`evidence_paragraphs` 去重并排序；`confidence` 取 max。  

3. **测试**  
   - `tests/test_field_refine_chunking.py`：纯函数级（切段、合并），**无 HTTP**。  

4. **文档**  
   - `.env.example`、`README`（精提小节）、`docs/DIFY_GAP_ANALYSIS.md` 已同步。  

## 未做

- 分段 **并发**、与 Dify 完全一致的切片边界（段落/标题）。  
