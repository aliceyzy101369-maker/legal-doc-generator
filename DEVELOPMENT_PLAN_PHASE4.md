# 合同审查程序 — 第四阶段（HTTP 取数 + 并发可配置）

## 交付

1. **`HttpDocumentProvider`**（`CONTRACT_DOCUMENT_PROVIDER=http`）  
   - `CONTRACT_DOCUMENT_HTTP_BASE_URL`（必填）  
   - `CONTRACT_DOCUMENT_HTTP_PATH_TEMPLATE`（默认 `/documents/{doc_id}`，支持 `{document_id}`）  
   - `CONTRACT_DOCUMENT_HTTP_TIMEOUT`（秒）  
   - `CONTRACT_DOCUMENT_HTTP_BEARER_TOKEN`（可选）  
   - TLS 使用与 LLM 相同的 `SSL_CERT_FILE` 逻辑  
   - JSON 响应从常见字段（`text` / `content` / `data` 等）抽取正文；非 JSON 则整体作为文本  

2. **审查并发**  
   - 环境变量 `REVIEW_TASK_MAX_WORKERS`（默认 **10**，与 Dify 迭代器常见配置对齐；范围 clamp 1–32）  
   - `summary.review_max_workers` / dry-run 同步暴露  

3. **附件拉取容错**  
   - 附件 id 拉取出现 `DocumentProviderConfigError` 时记入 `input_warnings`，并追加空占位，**不整单失败**（主合同 id 仍严格失败）。  

4. **测试**  
   - `tests/test_http_document_provider.py`（`urlopen` 全 mock）  

## 后续建议

- 按实际合同平台补充鉴权（如签名 Header、租户前缀 URL）。  
- JSON 抽取路径可配置（如 `$.data.textContent`）以减少适配代码。
