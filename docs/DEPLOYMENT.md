# 生产部署说明

本文描述合同审查 API 在生产环境常见的配置项、TLS、文档拉取与 LLM 切换，不涉及具体客户或合同全文。

## 环境变量清单（核心）

| 变量 | 说明 |
| --- | --- |
| `LLM_MODE` | `stub`（无远程调用）或 `real`（调用 OpenAI 兼容接口） |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | `LLM_MODE=real` 时必填；勿写入仓库或日志正文 |
| `CONTRACT_DOCUMENT_PROVIDER` | `stub`（内置假数据）、`http`（HTTP 拉取正文）、`none`（禁止仅用远程 id） |
| `CONTRACT_DOCUMENT_HTTP_BASE_URL` / `CONTRACT_DOCUMENT_HTTP_PATH_TEMPLATE` / `CONTRACT_DOCUMENT_HTTP_TIMEOUT` | HTTP 拉取主/附件 |
| `CONTRACT_DOCUMENT_HTTP_METHOD` / `CONTRACT_DOCUMENT_HTTP_BODY_TEMPLATE` | POST 时使用 JSON 模板，`{doc_id}` 占位 |
| `CONTRACT_DOCUMENT_HTTP_JSON_PATH` | 从 JSON 响应中取正文的点路径 |
| `CONTRACT_DOCUMENT_HTTP_HEADERS` | JSON 对象，额外请求头（租户、网关令牌等） |
| `CONTRACT_DOCUMENT_HTTP_SIGN_SECRET` / `CONTRACT_DOCUMENT_HTTP_SIGN_HEADER` | 可选：对 POST body 做 HMAC-SHA256 并写入指定头 |
| `SSL_CERT_FILE` | 指向 `certifi` 的 `cacert.pem` 或企业根证书，修复不完整证书链 |
| `REVIEW_TASK_MAX_WORKERS` | 审查子任务线程池上限，默认 `10`，范围建议 `1`–`32`；与上游 API 限流冲突时先降到 `4`–`6` |
| `FIELD_REFINE_CHUNK_MAX_WORKERS` | 精提分块并行，默认较低；限流时保持 `1` |
| `FIELD_EXTRACTION_INCLUDE_IN_REVIEW` | 是否在正式 `/reviews` 响应中带完整 §5.1 任务列表（体积大） |
| `FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS` | 任务行内 `source_preview` 最大长度 |
| `CORS_ORIGINS` | 逗号分隔浏览器源；设为空字符串可关闭 CORS 中间件 |

更全列表见仓库根目录 `.env.example`。

## 反向代理与 CORS

- 将公网 HTTPS 终止在 Nginx / 负载均衡，反代到 `uvicorn`（如 `127.0.0.1:8000`）。
- 若浏览器直接调 API，在服务端配置 `CORS_ORIGINS` 为前端源（如 `https://review.example.com`），**勿**使用 `*` 搭配携带 Cookie 的场景。
- 建议反代层统一注入 `X-Request-Id` / `trace_id` 相关头，便于与 `summary.trace_id` 对齐排查。

## `SSL_CERT_FILE`

在部分 Linux 或容器内若出现 `CERTIFICATE_VERIFY_FAILED`，设置：

```bash
export SSL_CERT_FILE="$(python3 -c "import certifi; print(certifi.where())")"
```

企业 MITM 或私有 CA 时，改为合并后的 PEM 路径。

## `CONTRACT_DOCUMENT_PROVIDER` 选择

- **`stub`**：联调、无外部合同系统；远程 id 返回占位正文。
- **`http`**：生产从合同 SaaS / 网关拉取；在网关完成 OAuth 后，本服务仅用固定 Header 或 HMAC 签名即可。
- **`none`**：禁止仅依赖远程 id、强制上传文件或内联 `text`。

## 切换到 `LLM_MODE=real`

1. 配置 `LLM_API_KEY`、`LLM_BASE_URL`（无尾部斜杠亦可）、`LLM_MODEL`。
2. 确认出站网络、TLS 与 `SSL_CERT_FILE`。
3. 日志与监控：**不要**记录完整模型返回或合同全文；本仓库已对 LLM 输出做截断与清洗，部署侧仍需关闭 body 全量 dump。

## 签名头（文档 HTTP）

当 `CONTRACT_DOCUMENT_HTTP_SIGN_SECRET` 非空时，对序列化后的请求体计算 HMAC-SHA256，写入 `CONTRACT_DOCUMENT_HTTP_SIGN_HEADER` 指定名称。具体网关字段名由对方文档约定。

## 并发参数推荐

| 场景 | `REVIEW_TASK_MAX_WORKERS` | `FIELD_REFINE_CHUNK_MAX_WORKERS` |
| --- | --- | --- |
| 默认（对齐 Dify 常见迭代并发） | `10` | `1`–`4` |
| 上游 LLM 强限流 | `4`–`6` | `1` |
| 单机 CPU 紧张、任务极多 | `4` | `1` |

结合 `FIELD_REFINE_CHUNK_SIZE`、`FIELD_REFINE_MAX_CHUNKS` 控制精提总调用量。

## OAuth 与网关门面（部署侧弥补「平台 OAuth」差距）

本服务不实现某一 SaaS 的 OAuth 授权码流程。推荐做法：

1. **反向代理 / API 网关**：代表用户完成 OAuth，将得到的 **Bearer** 或 **短期 API Key** 注入到本服务拉取合同所用的请求头（与 `CONTRACT_DOCUMENT_HTTP_HEADERS` 对齐），或把合同正文缓存在对象存储后由调用方只传 `text` / `file_path`。
2. **Sidecar**：与 `uvicorn` 同机部署小服务，把 `{doc_id}` 换为带鉴权的真实 URL 或代理拉取，本服务仍走 `http` provider 调 sidecar。
3. **不要在仓库或日志中**写入刷新令牌、长期密钥；生产用密钥管理（K8s Secret、Vault 等）。

与 **HMAC 请求体签名**（`CONTRACT_DOCUMENT_HTTP_SIGN_SECRET`）可组合使用：网关负责 OAuth，本服务负责按文档约定对 POST body 签名。

## 进程与发布

- 使用 `uvicorn contract_review_api.main:app --host 0.0.0.0 --port 8000` 或 gunicorn + uvicorn worker。
- 前端 `frontend/`：`npm ci && npm run build`，将 `dist/` 静态资源交给 CDN 或 Nginx；`vite` 开发代理仅用于本地。

## 前端构建变量

生产前端若需直连另一域名 API，在构建时注入 `VITE_*` 或等价代理（见 `frontend` 配置），避免把密钥写进前端包。
