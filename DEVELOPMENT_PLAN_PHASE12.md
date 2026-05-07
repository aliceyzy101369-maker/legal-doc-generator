# 第十二阶段：§5.1 任务行内联来源预览（dry-run）

## 方案

- 仅在 **`POST /reviews/dry-run`** 的 `summary.field_extraction_tasks` 中，对 `mode_1` / `mode_23` 每一行根据 **`src`** 从 **`source_library`** 取正文，附加：
  - `source_matched_src`、`source_full_len`
  - `source_preview`（截断）、`source_preview_truncated`
- **`POST /reviews`** 仍不包含任务正文预览（仅 `field_extraction_task_counts`），避免生产响应膨胀。

## 环境变量

- **`FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS`**（默认 **6000**，上限 **100000**；**0** 表示不写预览字符串，只保留长度字段）

## 实现位置

- `contract_review_api/services/field_extraction_tasks.py`：`enrich_field_extraction_tasks_with_sources`
- `contract_review_api/core/pipeline.py`：dry-run 组装时调用
