# 合同审查 API 服务

基于 **FastAPI** 的独立合同审查后端：从合同文本（或本地文件路径）提取关键字段、加载审查规则、组装审查任务、调用大模型（DeepSeek，OpenAI 兼容接口）生成审查意见，并输出结构化的 `comment_list` + `extracted_info`。

## 功能简介

- 接收合同：`text` 纯文本，或 `file_path` 指向本地 `.txt` / `.md` / `.docx` / `.pdf`
- 字段提取：正则/启发式抽取（如甲方、乙方、项目名称、合同期限等）
- 规则加载：内置 `base-rules` / `demo` / `strict-rules`，并支持从 `contract_review_api/rulesets/*.json` 扩展
- 审查任务：按 Dify 工作流思路构建任务包，支持长度分组、锚点分组、`empty_policy` 跳过
- 大模型审查：`LLM_MODE=stub|real`；真实模式支持 `SSL_CERT_FILE` 指定 CA bundle
- 输出：`final_output.comment_list`（4 键/7 键约束）与 `extracted_info`

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
- `docs/workflow_full_backup.md` / `docs/workflow_mapping.md`：Dify 工作流对照
- `docs/DIFY_GAP_ANALYSIS.md`：与 Dify 的差距分析（✅/⚠️/❌）

## 许可证

MIT（如仓库另有声明以仓库为准）。
