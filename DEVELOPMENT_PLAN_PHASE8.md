# 第八阶段：精提分段并发

## 交付

1. **`FIELD_REFINE_CHUNK_MAX_WORKERS`**（默认 **1**）  
   - `1`：与第七阶段一致，分段 **顺序** 请求。  
   - `>1`：`ThreadPoolExecutor` 并行调用各段 `_run_llm_field_extraction_one`，**按块下标排序后**再 `_merge_llm_field_map_parts`，保证与顺序合并语义一致。  
   - 上限 **16**（防刷爆线程与 API）。  

2. **可观测性**  
   - 多段且 `workers>1`：`summary` 侧无直接字段；`warnings` 增加 `llm_field_refine_chunk_parallel:<n>`。  
   - 单段 `fut.result()` 异常：`llm_field_refine_chunk_worker_error:<类型>`，该段视为空结果，其它段仍合并。  
   - `logger.info` 一行：`chunk_count` / `workers` / `field_name_count`（无正文）。  

3. **测试**  
   - `_run_llm_field_extraction_chunks` 支持注入 `extraction_fn`（单测用，避免线程内 monkeypatch 歧义）。  
   - `tests/test_field_refine_chunking.py`：并行完成顺序、worker 异常隔离、端到端 parallel warning。  

4. **文档**  
   - `.env.example`、`README`、`docs/DIFY_GAP_ANALYSIS.md`、`docs/DIFY_ACCEPTANCE_MATRIX.md`。  

## 未做

- 按 **段落/标题** 的智能切分；与 Dify 画布完全一致的并发度策略。  
