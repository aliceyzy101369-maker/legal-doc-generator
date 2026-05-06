# Dify 对齐 — 验收矩阵（第三阶段）

> 目的：把“能否替代 Dify”从口号拆成可执行的验收项。状态取值：**通过** / **部分** / **未覆盖**。  
> “部分”表示主链已接入但与 Dify 画布语义或数据形态仍有差异，需用真实合同样本复核。

| 验收项 | Dify 行为（摘要） | 当前 API 行为（摘要） | 状态 | 验收方法 |
|--------|-------------------|------------------------|------|----------|
| 入参解析 | `params.input` JSON：文本、ruleset、合同类型、主/附件 id 等 | `ReviewCreateRequest`：`text` / 本地路径 / `contract_id` 等别名 / `trace_id` | 部分 | `tests/test_phase3_remote_input.py`、`tests/test_dify_acceptance.py` |
| 主合同文本获取 | 工具按 id 拉取 `textContent` | `stub` / **`http`（可配置 BASE_URL + path 模板 + Bearer）** / `none` | 部分 | HTTP 为**通用**适配层，非某一固定 SaaS；需按实际 API 调路径与 JSON 字段 |
| 附件获取 | 迭代器拉附件并合并 | 远程 `attachment_ids` + 本地 `attachment_paths`；缺失附件记 `input_warnings` 不 500 | 部分 | `test_phase3_remote_input`、`case_with_attachments.json` |
| markdown 行解析 | `pid##category##text` 行级文本 | `markdown_line_parser` + 主文本启发式切换；dry-run 输出 `markdown_line_records`（无正文，仅 pid/len） | 部分 | `tests/test_markdown_line_parser.py`、`case_markdown_lines.json` |
| 粗提 | mode_1 多轮/切片 | `extract_field_candidates_coarse`：全量正则命中 | 部分 | 对照合同样本；`summary.coarse_field_count` |
| 精提 | mode_23 补全规范化 | `refine_field_candidates`：合流 + 规则 `target_fields` 占位补全 | 部分 | `summary.refined_field_count`；与 Dify 精提 LLM 仍可能不一致 |
| 规则加载 | ruleset API | `ruleset_loader` 内置 + JSON 文件 | 通过 | `tests/test_ruleset_loader.py` |
| 审查任务构建 | 回填、empty_policy、anchor、limit | `build_review_tasks` 未改语义 | 通过 | `tests/test_review_task_builder.py` |
| empty_policy | 全空跳过 | 已实现 | 通过 | 同上 |
| 锚点分组 | `src=0` 同组 | 已实现 | 通过 | 同上 |
| limit 切片 | 8000 等 | `chunk_tasks` 在任务构建之后 | 通过 | `tests/test_text_processing_chunk_tasks.py` |
| LLM 清洗链 | think/围栏/JSON | `llm_cleaner` + dict 外包一层容错 | 通过 | `tests/test_llm_cleaner.py` |
| 并发审查 | 迭代器并发 10 | `REVIEW_TASK_MAX_WORKERS`（默认 10，clamp 1–32） | 部分 | 默认值对齐；任务粒度仍取决于规则分组 |
| 错误隔离 | 子任务失败不拖垮 | 降级 issue + `error_count` | 通过 | `tests/test_summary_observability.py` |
| 合流节点 | 同字段 `\n` 拼接；合同类型强制 | `merge_fields` + `contract_type` | 通过 | `tests/test_result_merge.py` |
| 输出标准化 | 4/7 键 | `output_transform` | 通过 | `tests/test_output_transform.py` |
| summary | 多维统计 | `trace_id`、`llm_call_count`、`degraded_count`、`chunk_count`、`attachment_count`、粗/精提计数等 | 部分 | `tests/test_integration.py`、`test_summary_observability.py` |
| dry-run 可观测性 | 任务结构可解释 | `markdown_line_records`、warnings、粗/精提计数 | 部分 | `tests/test_dify_acceptance.py` |

## 结论摘要

- **已通过自动化验收**：入参扩展（stub）、Markdown 行解析、粗/精提计数、summary 可观测性、远程附件软失败、本地附件合并。  
- **仍需真实环境对照**：远程 HTTP provider、Dify 同款并发度与双链路 LLM 精提、聚合器与行级 markdown 全量兼容（含历史过滤词）。
