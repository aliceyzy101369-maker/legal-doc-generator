# Dify 工作流 vs 本仓库实现 — 差距分析

> 标注规则（按补充约束）：**仅主链 `pipeline.py` 实际调用的能力可标 ✅**；函数存在但未接入主链标 **⚠️**；未实现标 **❌**。  
> 本文基于 `docs/workflow_full_backup.md`、`docs/workflow_mapping.md` 与当前代码对照整理（**第十一阶段已更新**）。

## 总览


| Dify 节点 / 能力         | 主要代码位置                                                                                 | 状态  | 说明                                                                                                                                                                                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------- | --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 调取入参内容               | `api/schemas.py` + `services/input_ingest.py`                                          | ✅   | `text` / 路径 / 主附件 **id**；`trace_id`；`contract_type`；`**contract_subject` / `business_info` / `enterprise_list`**（来源库 src_1 / src_4）；`summary.source_slot_lens`                                                                                                     |
| 获取合同文本 / 附件（远程 id）   | `services/document_provider.py` + `input_ingest.gather_resolved_contract_bundle`       | ⚠️  | **stub** 内存表；**http** 可配置路径模板、**JSON 点路径**正文抽取、**额外 Header**；`none` 禁用；附件拉取失败软降级                                                                                                                                                                                   |
| 获取合同文本 / 附件 markdown | `services/text_processing.py`                                                          | ⚠️  | 本地文件 + 远程拉取文本合并；行级段落构建见下行                                                                                                                                                                                                                                          |
| Dify 行级 markdown     | `services/markdown_line_parser.py` + `text_processing.build_paragraphs`                | ⚠️  | `pid##category##text` 解析；**段落构建**仅保留 `category` 为 **number / nuber**（大小写不敏感）的行，对齐 Dify A/B 分支过滤词                                                                                                                                                                   |
| 构建字段取值来源库（src_1..4）  | `services/source_library.py` + `core/pipeline.py`                                      | ✅   | `build_source_library` 固定 4 项；`assemble_source_inputs` 从主文/附件路径组装；**精提 LLM** 优先用 `format_source_library_for_llm`；无独立持久化 JSON 产物                                                                                                                                    |
| 获取审查规则集 / 展开 rules   | `services/ruleset_loader.py`                                                           | ✅   | 内置 + 文件 ruleset                                                                                                                                                                                                                                                    |
| 构建待审对象字段库            | `services/pending_field_library.py` + `core/pipeline.py`                               | ✅   | `build_pending_object_field_library` 按工作流 4.4 过滤 `target_fields`（去 `src==0` / `mode==0`）、按 `name` 去重；**dry-run** `summary.source_library` + `pending_object_field_library`；正式 `**summary.pending_object_field_library`** + `**source_library_meta`**（仅长度，避免重复超大正文） |
| 构建字段提取任务（§5.1）       | `services/field_extraction_tasks.py` + `pipeline.py`                                   | ⚠️  | **dry-run**：`field_extraction_tasks` 每行带 `**source_preview`**（`src→content` 截断，可配置）；**正式**：仅 `field_extraction_task_counts`                                                                                                                                        |
| 粗提 / 精提双链路           | `services/field_extraction.py` + `pipeline.py` + `llm_engine.run_llm_field_extraction` | ⚠️  | **粗提**=正则；**默认** `FIELD_REFINE_MODE=regex` = 合流 + 规则占位；**llm** = 来源库/全文 LLM 抽取，与粗提 **\n 拼接**；`LLM_MODE=real` 下多段合并，**换行软切分**（可关）+ 可选 **并行**；**未**复刻 Dify **标题/空行段落级**切片                                                                                             |
| 粗提/精提切片（limit=8000）  | `services/text_processing.py` + `core/pipeline.py`                                     | ✅   | `chunk_tasks` 在任务构建之后                                                                                                                                                                                                                                              |
| 构建审查任务队列             | `services/review_task_builder.py` + `pipeline.py`                                      | ✅   | 回填、`empty_policy`、anchor、limit                                                                                                                                                                                                                                     |
| 迭代器并发审查              | `core/pipeline.py`                                                                     | ⚠️  | `REVIEW_TASK_MAX_WORKERS`（默认 10，可改）；与 Dify 画布并发仍可能因任务拆分不同而不等价                                                                                                                                                                                                      |
| 审查（LLM）              | `services/llm_engine.py`                                                               | ✅   | 超时、SSL、`degraded` 可计数                                                                                                                                                                                                                                              |
| 审查后处理链               | `services/llm_cleaner.py`                                                              | ✅   | think / 围栏 / JSON + dict 外包一层                                                                                                                                                                                                                                      |
| 输出数据格式校验             | `services/output_transform.py`                                                         | ✅   | 4/7 键、`normalize_review_issues`                                                                                                                                                                                                                                    |
| 构建待审文本库（合流）          | `services/result_merge.py`                                                             | ✅   | 同键 `\n` 拼接；`contract_type` 入参强制                                                                                                                                                                                                                                    |
| 审查聚合器                | `services/result_merge.py`                                                             | ⚠️  | **去重**：`title`+`comment` 哈希；**排序**：严重度降序再 `title`；**final_output**：仅排除标题为 **模型审查降级提示** 的项（业务类「字段粗提降级」仍进 `comment_list`）；`summary.aggregation_success_count` / `aggregation_error_count`                                                                            |
| 最终输出 / 渲染            | `services/report_render.py`                                                            | ⚠️  | Markdown 较简                                                                                                                                                                                                                                                        |
| 验收矩阵                 | `docs/DIFY_ACCEPTANCE_MATRIX.md`                                                       | ✅   | 可逐项对照                                                                                                                                                                                                                                                              |


## 仍建议优先补齐的方向（❌/⚠️ 集中区）

1. **HTTP 与具体合同平台对齐**：签名字段、OAuth、非 GET 等。
2. **精提与 Dify 完全等价**：切片边界（段落/标题）、与来源库逐段对齐及画布级并发策略。
3. **附件 / 主文 markdown**：除 number/nuber 外若仍有历史 category 需兼容，可扩展白名单或配置。

## 剩余差距与建议（第六阶段后）


| 优先级 | 项               | 说明                                       |
| --- | --------------- | ---------------------------------------- |
| 高   | 精提多段 LLM        | 超长合同按 Dify 迭代切片并发抽取，避免单次截断               |
| 中   | 审查聚合与 Dify 画布   | 多分支合并规则、errorCollection 与画布节点一一对照        |
| 中   | Remote HTTP     | 生产级鉴权与非 GET                              |
| 低   | 工作流 §5.1 全量正文内联 | dry-run 默认预览非全文；若需整段 `src` 正文可提预览上限或另开导出 |
