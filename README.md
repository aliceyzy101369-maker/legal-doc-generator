# 合同审查 API 服务

基于 **FastAPI** 的独立合同审查后端：从合同文本（或本地文件路径）提取关键字段、加载审查规则、组装审查任务、调用大模型（DeepSeek，OpenAI 兼容接口）生成审查意见，并输出结构化的 `comment_list` + `extracted_info`。

第三阶段目标：在**不依赖真实 Dify 画布**的前提下，补齐 **Dify 风格入参**、**行级 markdown 解析**、**粗提/精提可观测性**与 **验收矩阵**，使「替代程度」可对照 `docs/DIFY_ACCEPTANCE_MATRIX.md` 逐项验收。

第四阶段补充：**通用 HTTP 合同拉取**（可配置 base URL + path 模板 + Bearer）、**审查并发数** `REVIEW_TASK_MAX_WORKERS`（默认 10），详见 `DEVELOPMENT_PLAN_PHASE4.md`。

## 功能简介

- **输入方式**
  - `text` 纯文本；或 `file_path` + 可选 `attachment_paths`（本地 `.txt` / `.md` / `.docx` / `.pdf`）
  - Dify 风格 **主合同 id**：`contract_id` / `main_contract_id` / `file_id`（经可插拔 `DocumentProvider` 解析；默认 **stub** 内存假数据）
  - **附件 id**：`attachment_ids`、`file_ids`、`files`（别名列表）；缺失 id 记入 `summary.input_warnings`，**不导致整单 500**
  - `trace_id`：可选；未传则服务端生成 UUID，并写入 `summary.trace_id` 与结构化日志（**不记录合同全文**）
  - **来源库补充（Dify §2.2 / src_1·src_4）**：`contract_subject`（写入来源库 **src=1**）、`business_info` 与 `enterprise_list`（合并写入 **src=4**）；`summary.source_slot_lens` 返回两槽字符长度
- **字段提取（粗提 / 精提）**
  - **粗提**：`extract_field_candidates_coarse`（全量正则命中，`summary.coarse_field_count`）
  - **精提**：`refine_field_candidates`（默认 `FIELD_REFINE_MODE=regex` 或 `rules`：合流 + 规则 `target_fields` 占位，无字段 LLM）；`FIELD_REFINE_MODE=llm` 或 `LLM_FIELD_REFINE=true` 时以 **来源库 src=1..4**（`source_library.py`）序列化文本调用 LLM 抽取；**超长**时在 `LLM_MODE=real` 下按 `FIELD_REFINE_CHUNK_SIZE`（默认 8000，下限 2000）**分段请求**并合并；默认 **`FIELD_REFINE_CHUNK_SOFT_BREAK`** 在块尾窗口内优先 **换行处切断**（第九阶段）；`FIELD_REFINE_CHUNK_MAX_WORKERS>1` 时段内 **并行**（仍按下标顺序合并）；与粗提同字段 **\\n 拼接**；`LLM_MODE=stub` 时不发起抽取请求。
  - `summary.refined_field_count`；粗提为空时追加可理解的降级提示 issue
- **Dify markdown 行**：`pid##分类##正文` — `services/markdown_line_parser.py`；主文符合启发式时走行级段落，`dry-run` 返回 `markdown_line_records`（仅 pid、分类与 `text_len`，不含正文）
- **规则与任务**：`empty_policy`、锚点分组、`chunk_tasks` 切片、并发 LLM（worker=5，与 Dify 默认 10 不完全一致）
- **可观测性**：`summary` 含 `llm_call_count`、`degraded_count`、`chunk_count`、`attachment_count`、`input_warnings` 等
- **模式**：`LLM_MODE=stub|real`；真实模式支持 `SSL_CERT_FILE`

### stub / real

- **stub**：不发起远程 LLM；测试与 CI 默认使用。
- **real**：需配置 `LLM_*`；仍应通过 `SSL_CERT_FILE` 解决证书链问题（见 `.env.example`）。

### dry-run

`POST /reviews/dry-run` 不写入持久化存储，用于验收：**审查任务列表**、粗/精提计数、markdown 解析摘要、附件告警等。

### 当前状态（与 Dify 替代）

- **主链能力与可观测性**已与 `docs/DIFY_GAP_ANALYSIS.md`（第十五阶段）对齐；具体 SaaS 的 OAuth 在网关侧配置，或使用 HTTP 扩展头 / **POST body HMAC**（`.env.example`）。
- 与**某一线上 Dify 应用**输出完全一致需同一规则集与模型及 golden 样本对照，属验收而非代码缺口。

**完整对照与阶段索引**：[`docs/WORKFLOW_TO_API.md`](docs/WORKFLOW_TO_API.md)（节点→API）、[`docs/DEVELOPMENT_MASTER.md`](docs/DEVELOPMENT_MASTER.md)（各 `DEVELOPMENT_PLAN_PHASE*.md` 索引）。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

复制示例环境文件并按需填写（**不要**把真实 `.env` 提交到 Git）：

```bash
cp .env.example .env
```

常用变量：

- `FIELD_REFINE_CHUNK_STRATEGY`：`soft_newline`（默认）｜`hard`｜`markdown_heading`（精提 LLM 分段策略，第十五阶段）
- `LLM_MODE`：`stub`（默认，离线）或 `real`
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`：真实模型调用
- `SSL_CERT_FILE`：指向 `certifi` 的 `cacert.pem`（macOS 上常见 SSL 修复）
- `CONTRACT_DOCUMENT_PROVIDER`：`stub`（默认，内存 id→文本）、`http`（按环境变量 HTTP 拉取）、`none`（禁止按 id 取数）
- `CONTRACT_DOCUMENT_HTTP_*`（`METHOD`=`GET`|`POST`、`BODY_TEMPLATE` 含 `{doc_id}`/`{document_id}` 占位符、可选 `JSON_PATH`、`HEADERS`）、`REVIEW_TASK_MAX_WORKERS`：见 `.env.example`
- `FIELD_REFINE_MODE`、`LLM_FIELD_REFINE`、`FIELD_REFINE_TEXT_LIMIT`、`FIELD_REFINE_LLM_TIMEOUT`、`FIELD_REFINE_CHUNK_SIZE`、`FIELD_REFINE_MAX_CHUNKS`、`FIELD_REFINE_USE_CHUNKS`、`FIELD_REFINE_CHUNK_MAX_WORKERS`、`FIELD_REFINE_CHUNK_SOFT_BREAK`、`FIELD_REFINE_CHUNK_BREAK_WINDOW`：精提 LLM 路径（第六至九阶段）
- **工作流可观测**：`summary.pending_object_field_library`（§4.4）、`summary.source_library_meta`、**`summary.field_extraction_task_counts`**（§5.1）；**dry-run** 含完整 `source_library`、**`field_extraction_tasks`**；**正式 `/reviews`** 可通过请求体 **`include_field_extraction_tasks`** 或环境变量 **`FIELD_EXTRACTION_INCLUDE_IN_REVIEW`** 附带同款任务列表（每行 `source_preview` 等，`FIELD_EXTRACTION_SOURCE_PREVIEW_CHARS` 可调）
- **Markdown 段落类目**：默认仅 `number`/`nuber` 进入段落；**`MARKDOWN_PARAGRAPH_CATEGORY_ALLOWLIST`** 可扩展（逗号分隔），对齐历史 Dify 类目

请求体可选字段 `contract_type`：若提供，将**强制覆盖**合并后的 `contract_type` 字段（对齐 Dify「入参合同类型」语义）。

## 启动服务

```bash
uvicorn contract_review_api.main:app --reload
```

默认文档：`http://127.0.0.1:8000/docs`

## 前端（Vite + React）

`frontend/` 提供最小可用的审查界面：选择规则集、粘贴合同文本或上传主合同/附件（`.txt` / `.md` / `.docx` / `.pdf`），调用后端并展示 `comment_list` 与 `extracted_info`。**验收 dry-run**（仅粘贴文本）：调用 `POST /reviews/dry-run` 查看任务与 `summary`。**高级选项**（折叠面板）：`contract_subject` / `business_info` / `enterprise_list`、是否附带 `include_field_extraction_tasks`；结果区展示 `trace_id`、非空的 `error_collection` 与 Markdown 报告折叠块。

1. **启动后端**（与 Vite 代理目标一致，默认 8000）：
   ```bash
   uvicorn contract_review_api.main:app --reload --port 8000
   ```
2. **启动前端**：
   ```bash
   cd frontend && npm install && npm run dev
   ```
   浏览器打开终端提示的地址（一般为 `http://localhost:5173`）。开发时，`vite.config.ts` 将 `/reviews`、`/rulesets`、`/health` **代理**到 `http://127.0.0.1:8000`，无需在前端写死完整 API 域名。
3. **CORS**：后端默认允许 `http://localhost:5173` 与 `http://127.0.0.1:5173`（环境变量 **`CORS_ORIGINS`**，逗号分隔多个 Origin）。若将前后端分域部署，请在 `.env` 中配置允许的 Origin；将 **`CORS_ORIGINS` 设为空字符串** 可关闭 CORS 中间件（仅适合同源或纯代理场景）。

生产构建：`cd frontend && npm run build`，产物在 `frontend/dist`；需自行配置静态托管，并把浏览器请求指向你的 API 基地址（或网关同源反代）。

## API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/rulesets` | 列出可用规则集 id |
| POST | `/reviews` | 执行完整审查流程 |
| POST | `/reviews/upload` | `multipart/form-data`：主合同文件、可选附件、表单字段（与 JSON 入参语义对齐） |
| POST | `/reviews/dry-run` | 仅构建审查任务与摘要（不落库） |

## 运行测试

```bash
python3 -m pytest tests/ -v
```

CI（GitHub Actions）：任意分支 `push` 或向 `main` 的 PR 运行 **pytest**（Python 3.11，`LLM_MODE=stub`）与 **`frontend` 的 `npm ci` + 生产构建**（Node 20，见 `.github/workflows/ci.yml`）。

## 相关文档

- `DEVELOPMENT_PLAN.md`：第一阶段任务清单
- `DEVELOPMENT_PLAN_PHASE3.md`：第三阶段执行说明（摘要）
- `DEVELOPMENT_PLAN_PHASE4.md`：HTTP 取数与并发配置
- `docs/workflow_full_backup.md` / `docs/workflow_mapping.md`：Dify 工作流对照
- `docs/DIFY_GAP_ANALYSIS.md`：与 Dify 的差距分析（✅/⚠️/❌）
- `docs/DIFY_ACCEPTANCE_MATRIX.md`：验收矩阵与结论摘要

## 许可证

MIT（如仓库另有声明以仓库为准）。
