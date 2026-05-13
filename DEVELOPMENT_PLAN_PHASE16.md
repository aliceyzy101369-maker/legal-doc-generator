# 第十六阶段 — CI、dry-run 前端、golden 回归与部署文档

## 目标

在 `main` 上收口工程化与可观测性：GitHub Actions 矩阵（Python 3.11 + Node 20）、前端 dry-run 与 `error_collection` 体验、`summary.error_collection[].source`、脱敏 golden 样本回归、`docs/DEPLOYMENT.md`。

## 交付

1. **`.github/workflows/ci.yml`**：`push` 任意分支 + `pull_request` 至 `main`；后端 `pip install -r requirements.txt` → `pytest`（`LLM_MODE=stub`）；前端 `npm ci` → `npm run build`。
2. **`.gitignore`**：`docs/ORIGINAL_DIFY_WORKFLOW_DISCUSSION.md` 保持本地忽略（不入库）。
3. **前端**：`仅 dry-run` 按钮与 dry-run 面板（`review_task_count`、`field_extraction_task_counts`、`markdown_line_records`、`source_library` 概览、折叠 `field_extraction_tasks` 最多 50 行）；`error_collection` 可展开查看 `comment` 全文。
4. **后端**：`error_collection` 每项含 `source`（`llm_subtask` / `document_fetch` / `field_refine`）；附件/精提告警可映射为基础设施降级项。
5. **`tests/fixtures/golden/`**：`sample_purchase.json`、`sample_service.json`（各含脱敏 `text` + `expect` 上下界：`field_count` / `issue_count` / `aggregation_success_count`）；`tests/test_golden_regression.py`（默认 `LLM_MODE=stub`，范围断言）。
6. **`docs/DEPLOYMENT.md`**：生产环境变量、反代/CORS、`SSL_CERT_FILE`、文档 Provider、`LLM_MODE=real`、签名头、并发建议。

## 未做项（留待后续）

- 与某一线上 Dify 应用的字节级 golden 全集（需同一规则 JSON + 同一模型）。
- 具体 SaaS OAuth 在网关侧的参考实现（本仓库仅提供 HTTP + 签名钩子）。

## 验证

```bash
python3 -m pytest tests/ -q
cd frontend && npm ci && npm run build
```
