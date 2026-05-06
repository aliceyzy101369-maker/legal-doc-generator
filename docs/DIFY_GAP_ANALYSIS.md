# Dify 工作流 vs 本仓库实现 — 差距分析

> 标注规则（按补充约束）：**仅主链 `pipeline.py` 实际调用的能力可标 ✅**；函数存在但未接入主链标 **⚠️**；未实现标 **❌**。  
> 本文基于 `docs/workflow_full_backup.md`、`docs/workflow_mapping.md` 与当前代码对照整理（**第三阶段已更新**）。

## 总览

| Dify 节点 / 能力 | 主要代码位置 | 状态 | 说明 |
|------------------|-------------|------|------|
| 调取入参内容 | `api/schemas.py` + `services/input_ingest.py` | ✅ | 支持 `text` / 本地路径 / 主/附件 **id**（经 `DocumentProvider`）；`trace_id`；`contract_type` 覆盖 |
| 获取合同文本 / 附件（远程 id） | `services/document_provider.py` + `input_ingest.gather_resolved_contract_bundle` | ⚠️ | **默认 stub** 内存表；`CONTRACT_DOCUMENT_PROVIDER=none` 显式禁用；**非** Dify 同款 HTTP 工具节点 |
| 获取合同文本 / 附件 markdown | `services/text_processing.py` | ⚠️ | 本地文件 + 远程拉取文本合并；**非** `pid##category##text` 全量历史过滤（`nuber`/`number`）行为 |
| Dify 行级 markdown | `services/markdown_line_parser.py` + `text_processing.build_paragraphs` | ⚠️ | 解析与主文启发式接入；**未**复刻附件分支过滤词差异等全部细节 |
| 构建字段取值来源库（src_1..4） | — | ❌ | 仍无独立 JSON「来源库」产物；段落 `doc_type` 表达部分来源 |
| 获取审查规则集 / 展开 rules | `services/ruleset_loader.py` | ✅ | 内置 + 文件 ruleset |
| 构建待审对象字段库 | `services/review_task_builder.py`（部分） | ⚠️ | 仍无 Dify 同名中间 JSON；逻辑在任务构建中体现 |
| 粗提 / 精提双链路 | `services/field_extraction.py` + `pipeline.py` | ⚠️ | **粗提**=全量正则命中；**精提**=合流 + 规则字段占位补全；与 Dify mode_1/mode_23 **不等价**（尤其 LLM 精提） |
| 粗提/精提切片（limit=8000） | `services/text_processing.py` + `core/pipeline.py` | ✅ | `chunk_tasks` 在任务构建之后 |
| 构建审查任务队列 | `services/review_task_builder.py` + `pipeline.py` | ✅ | 回填、`empty_policy`、anchor、limit |
| 迭代器并发审查 | `core/pipeline.py` | ⚠️ | `ThreadPoolExecutor(max_workers=5)`；Dify 常为 10 |
| 审查（LLM） | `services/llm_engine.py` | ✅ | 超时、SSL、`degraded` 可计数 |
| 审查后处理链 | `services/llm_cleaner.py` | ✅ | think / 围栏 / JSON + dict 外包一层 |
| 输出数据格式校验 | `services/output_transform.py` | ✅ | 4/7 键、`normalize_review_issues` |
| 构建待审文本库（合流） | `services/result_merge.py` | ✅ | 同键 `\n` 拼接；`contract_type` 入参强制 |
| 审查聚合器 | `services/result_merge.py` | ⚠️ | 哈希去重 + 严重度排序；与 Dify 多分支聚合仍可能不一致 |
| 最终输出 / 渲染 | `services/report_render.py` | ⚠️ | Markdown 较简 |
| 验收矩阵 | `docs/DIFY_ACCEPTANCE_MATRIX.md` | ✅ | 第三阶段新增，可逐项对照 |

## 仍建议优先补齐的方向（❌/⚠️ 集中区）

1. **真实 RemoteDocumentProvider（HTTP）**：与具体合同存储/ Dify 工具节点对齐，替代 stub。  
2. **Dify 粗提/精提 LLM 语义对齐**：当前精提以规则占位为主，不等价 mode_23。  
3. **附件 markdown 分支差异**（如 `nuber` vs `number`）与历史行格式的全量兼容。
