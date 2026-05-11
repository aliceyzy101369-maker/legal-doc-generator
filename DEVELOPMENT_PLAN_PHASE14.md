# 第十四阶段 — Dify 1:1 补强（可配置）

## 目标

缩小与 Dify 画布在「可观测性」与「远程取数形态」上的差距，且不默认增大正式审查响应体积。

## 交付

1. **§5.1 字段提取任务（正式 `/reviews`）**  
   - 请求体：`include_field_extraction_tasks`（`true`/`false`/`null`）。  
   - `null` 时读环境变量 **`FIELD_EXTRACTION_INCLUDE_IN_REVIEW`**（默认关）。  
   - 为 `true` 时，`summary.field_extraction_tasks` 与 dry-run 同形（含 `source_preview`，长度受 **`FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS`** 约束）。  
   - `POST /reviews/upload`：表单字段 **`include_field_extraction_tasks`**（可选布尔）。

2. **Dify 行级 markdown 段落类目**  
   - 环境变量 **`MARKDOWN_PARAGRAPH_CATEGORY_ALLOWLIST`**：逗号分隔，与默认的 `number`/`nuber` 合并，用于 `paragraphs_from_markdown_lines` 过滤。

3. **HTTP DocumentProvider：POST**  
   - **`CONTRACT_DOCUMENT_HTTP_METHOD`**：`GET`（默认）或 `POST`。  
   - **`CONTRACT_DOCUMENT_HTTP_BODY_TEMPLATE`**：JSON 字符串，使用占位 **`{doc_id}`** / **`{document_id}`**（按字面替换，避免与 JSON 花括号冲突）。未设置 POST body 时默认 `{"doc_id":"<id>"}`。

## 验证

```bash
python3 -m pytest tests/ -q
```

相关用例：`test_pipeline.test_review_full_run_can_include_field_extraction_tasks`、`test_markdown_line_parser.test_paragraph_allowlist_extends_categories`、`test_http_document_provider_post_*`。
