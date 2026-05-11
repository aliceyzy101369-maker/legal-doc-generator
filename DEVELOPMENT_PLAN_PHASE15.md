# 第十五阶段 — Dify 1:1 主链 closure

## 目标

在**不依赖具体 SaaS 账号**的前提下，将差距表中仍标 ⚠️ 的项以**可配置实现 + summary/报告可观测**方式收口，使主链与 `docs/DIFY_ACCEPTANCE_MATRIX.md` 的「可替代」结论一致。

## 交付

1. **精提分块策略 `FIELD_REFINE_CHUNK_STRATEGY`**
   - `soft_newline`（默认）、`hard`、`markdown_heading`（ATX 标题 `^#{1,6}\s` 切段后按 `FIELD_REFINE_CHUNK_SIZE` 打包，超大段回退为软换行切分）。

2. **`summary.error_collection`**
   - 与 `partition_issues_for_final_output` 中 **基础设施降级** 问题同构的 JSON 列表（对齐 Dify error / 聚合旁路可观测性）。

3. **Markdown 报告** `report_render.render_markdown`
   - 增加 trace、耗时、任务/切片统计、**error_collection** 专节。

4. **HTTP 文档拉取**
   - POST 请求体可选 **HMAC-SHA256** 签名头（`CONTRACT_DOCUMENT_HTTP_SIGN_SECRET` 等）；OAuth 仍由调用方在网关或环境侧处理。

## 验证

`python3 -m pytest tests/ -q`
