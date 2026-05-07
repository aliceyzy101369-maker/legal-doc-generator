# 第十阶段：工作流 4.4「待审对象字段库」可观测

## 目标

对齐 `docs/workflow_full_backup.md` **§4.4 构建待审对象字段库**：从已加载规则的 `target_fields` 导出待审字段定义，并在主链可观测。

## 交付

1. **`contract_review_api/services/pending_field_library.py`**  
   - `build_pending_object_field_library(rules)`：过滤非 dict、`name` 空、`src == 0` 或 `mode == 0`（整数比较，非法值跳过 0 判断）；按 `name` 去重（先出现者优先）；保留 `desc`、`rule_title` 等便于对账。

2. **`pipeline._prepare_contract_state`**  
   - 计算并放入 state：`pending_object_field_library`。

3. **`summary`（`POST /reviews`）**  
   - `pending_object_field_library`：列表（体量小）。  
   - `source_library_meta`：`[{src, content_len}, ...]` 四项，**不含正文**（避免与合同重复传输）。

4. **`POST /reviews/dry-run`**  
   - `summary.pending_object_field_library`  
   - `summary.source_library`：完整四项（与工作流 JSON 结构一致，便于调试）。  
   - `summary.source_library_meta`：同上。

5. **测试**  
   - `tests/test_pending_field_library.py`  
   - 扩展 `test_pipeline`、`test_integration`、`test_summary_observability`。

## 未做

- 与 Dify 完全一致的「待审字段库」**字符串化 JSON** 中间落盘；`mode_1` / `mode_23` **拆分任务列表** 独立产物（见工作流 §5.1）。  
