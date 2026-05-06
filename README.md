# 合同审查 API 服务

基于 **FastAPI** 的独立合同审查后端：从合同文本（或本地文件路径）提取关键字段、加载审查规则、组装审查任务、调用大模型（DeepSeek，OpenAI 兼容接口）生成审查意见，并输出结构化的 `comment_list` + `extracted_info`。

第三阶段目标：在**不依赖真实 Dify 画布**的前提下，补齐 **Dify 风格入参**、**行级 markdown 解析**、**粗提/精提可观测性**与 **验收矩阵**，使「替代程度」可对照 `docs/DIFY_ACCEPTANCE_MATRIX.md` 逐项验收。

## 功能简介

- **输入方式**
  - `text` 纯文本；或 `file_path` + 可选 `attachment_paths`（本地 `.txt` / `.md` / `.docx` / `.pdf`）
  - Dify 风格 **主合同 id**：`contract_id` / `main_contract_id` / `file_id`（经可插拔 `DocumentProvider` 解析；默认 **stub** 内存假数据）
  - **附件 id**：`attachment_ids`、`file_ids`、`files`（别名列表）；缺失 id 记入 `summary.input_warnings`，**不导致整单 500**
  - `trace_id`：可选；未传则服务端生成 UUID，并写入 `summary.trace_id` 与结构化日志（**不记录合同全文**）
- **字段提取（粗提 / 精提）**
  - **粗提**：`extract_field_candidates_coarse`（全量正则命中，`summary.coarse_field_count`）
  - **精提**：`refine_field_candidates`（合流 + 规则 `target_fields` 占位补全，`summary.refined_field_count`）；粗提为空时追加可理解的降级提示 issue
- **Dify markdown 行**：`pid##分类##正文` — `services/markdown_line_parser.py`；主文符合启发式时走行级段落，`dry-run` 返回 `markdown_line_records`（仅 pid、分类与 `text_len`，不含正文）
- **规则与任务**：`empty_policy`、锚点分组、`chunk_tasks` 切片、并发 LLM（worker=5，与 Dify 默认 10 不完全一致）
- **可观测性**：`summary` 含 `llm_call_count`、`degraded_count`、`chunk_count`、`attachment_count`、`input_warnings` 等
- **模式**：`LLM_MODE=stub|real`；真实模式支持 `SSL_CERT_FILE`

### stub / real

- **stub**：不发起远程 LLM；测试与 CI 默认使用。
- **real**：需配置 `LLM_*`；仍应通过 `SSL_CERT_FILE` 解决证书链问题（见 `.env.example`）。

### dry-run

`POST /reviews/dry-run` 不写入持久化存储，用于验收：**审查任务列表**、粗/精提计数、markdown 解析摘要、附件告警等。

### 当前限制（替代 Dify 程度）

- **无内置 HTTP 远程合同平台**：默认 `StubDocumentProvider`；`CONTRACT_DOCUMENT_PROVIDER=none` 时 **拒绝**仅用 id 的请求（400）。
- **粗/精提**与 Dify 双 LLM 链路可能仍不一致；请以 `docs/DIFY_GAP_ANALYSIS.md` 与验收矩阵为准。

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

- `LLM_MODE`：`stub`（默认，离线）或 `real`
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`：真实模型调用
- `SSL_CERT_FILE`：指向 `certifi` 的 `cacert.pem`（macOS 上常见 SSL 修复）
- `CONTRACT_DOCUMENT_PROVIDER`：`stub`（默认，内存 id→文本）或 `none`（禁止按 id 取数）

请求体可选字段 `contract_type`：若提供，将**强制覆盖**合并后的 `contract_type` 字段（对齐 Dify「入参合同类型」语义）。

## 启动服务

```bash
uvicorn contract_review_api.main:app --reload
```

默认文档：`http://127.0.0.1:8000/docs`

## API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/rulesets` | 列出可用规则集 id |
| POST | `/reviews` | 执行完整审查流程 |
| POST | `/reviews/dry-run` | 仅构建审查任务与摘要（不落库） |

## 运行测试

```bash
python3 -m pytest tests/ -v
```

## 相关文档

- `DEVELOPMENT_PLAN.md`：第一阶段任务清单
- `DEVELOPMENT_PLAN_PHASE3.md`：第三阶段执行说明（摘要）
- `docs/workflow_full_backup.md` / `docs/workflow_mapping.md`：Dify 工作流对照
- `docs/DIFY_GAP_ANALYSIS.md`：与 Dify 的差距分析（✅/⚠️/❌）
- `docs/DIFY_ACCEPTANCE_MATRIX.md`：验收矩阵与结论摘要

## 许可证

MIT（如仓库另有声明以仓库为准）。
