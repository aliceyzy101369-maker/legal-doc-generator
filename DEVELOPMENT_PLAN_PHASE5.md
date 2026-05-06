# 合同审查程序 — 第五阶段（HTTP 适配增强）

## 交付

1. **`CONTRACT_DOCUMENT_HTTP_JSON_PATH`**（可选）  
   - 点分路径从 JSON 响应中取合同正文，例如 `data.textContent`、`payload.result.markdown`。  
   - 支持列表下标：`blocks.0.text`。  
   - 未命中或值为非字符串标量时，**回退**到原有内置字段启发式，再回退原始 body。  

2. **`CONTRACT_DOCUMENT_HTTP_HEADERS`**（可选）  
   - 值为 **JSON 对象**字符串；键值对合并进请求头（值统一 `str()`），与 `Bearer` 可并存；非法 JSON 或非 object 在 `from_env` 时抛 `DocumentProviderConfigError`。  

3. **测试**  
   - `tests/test_http_document_provider.py` 覆盖嵌套路径、列表下标、自定义头、`from_env` 组合、非法 HEADERS JSON。  

4. **文档**  
   - `.env.example`、`README.md`、`docs/DIFY_GAP_ANALYSIS.md` 已同步。  

## 后续建议

- 若需 **JSON Pointer**（`/data/0/text`）或 **jq** 风格，可再扩展或引入轻量依赖。  
- 非 GET、请求体模板、按租户切换 base URL 等，按对接系统再补。  
