# Dify 工作流 vs 本仓库实现 — 差距分析

> 标注规则（按补充约束）：**仅主链 `pipeline.py` 实际调用的能力可标 ✅**；函数存在但未接入主链标 **⚠️**；未实现标 **❌**。  
> 本文基于 `docs/workflow_full_backup.md`、`docs/workflow_mapping.md` 与当前代码对照整理（**第十六阶段：CI、golden、部署文档与 error_collection 可观测**）。

## 总览


| Dify 节点 / 能力         | 主要代码位置                                                                                 | 状态  | 说明                                                                                                                                                                                                                                            |
| -------------------- | -------------------------------------------------------------------------------------- | --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 调取入参内容               | `api/schemas.py` + `services/input_ingest.py`                                          | ✅   | `text` / 路径 / 主附件 **id**；`trace_id`；`contract_type`；`contract_subject` / `business_info` / `enterprise_list`（来源库 src_1 / src_4）；`summary.source_slot_lens`                                                                                    |
| 获取合同文本 / 附件（远程 id）   | `services/document_provider.py` + `input_ingest.gather_resolved_contract_bundle`       | ✅   | **stub**；**http**：GET 或 **POST**（`CONTRACT_DOCUMENT_HTTP_BODY_TEMPLATE` 占位 `{doc_id}`）；可选 **HMAC-SHA256** 请求签名（`CONTRACT_DOCUMENT_HTTP_SIGN_SECRET`）；**JSON 点路径** + **Header**；`none` 禁用；附件缺失软降级。**具体 SaaS 的 OAuth** 由部署侧网关或调用方配置，不属于本仓库内置范围。 |
| 获取合同文本 / 附件 markdown | `services/text_processing.py`                                                          | ✅   | 本地 + 远程正文合并；行级段落见下行                                                                                                                                                                                                                           |
| Dify 行级 markdown     | `services/markdown_line_parser.py` + `text_processing.build_paragraphs`                | ✅   | `pid##category##text`；默认段落 **number / nuber**；环境变量 `MARKDOWN_PARAGRAPH_CATEGORY_ALLOWLIST` 扩展类目                                                                                                                                                |
| 构建字段取值来源库（src_1..4）  | `services/source_library.py` + `core/pipeline.py`                                      | ✅   | `build_source_library`；`assemble_source_inputs`；精提 LLM 用 `format_source_library_for_llm`                                                                                                                                                      |
| 获取审查规则集 / 展开 rules   | `services/ruleset_loader.py`                                                           | ✅   | 内置 + 文件 ruleset                                                                                                                                                                                                                               |
| 构建待审对象字段库            | `services/pending_field_library.py` + `core/pipeline.py`                               | ✅   | §4.4 过滤；dry-run / `summary.pending_object_field_library` + `source_library_meta`                                                                                                                                                              |
| 构建字段提取任务（§5.1）       | `services/field_extraction_tasks.py` + `pipeline.py`                                   | ✅   | dry-run 完整列表；正式默认计数；请求体 `include_field_extraction_tasks` / 环境变量 `FIELD_EXTRACTION_INCLUDE_IN_REVIEW` 输出完整列表                                                                                                                                    |
| 粗提 / 精提双链路           | `services/field_extraction.py` + `pipeline.py` + `llm_engine.run_llm_field_extraction` | ✅   | 粗提=正则；精提 **regex / llm**；`FIELD_REFINE_CHUNK_STRATEGY=markdown_heading` 提供标题级分段后再按上限打包（对齐 Dify 章节切片思路）；换行软切分 / 并行可配置                                                                                                                      |
| 粗提/精提切片（limit=8000）  | `services/text_processing.py` + `core/pipeline.py`                                     | ✅   | `chunk_tasks`（审查任务侧）                                                                                                                                                                                                                          |
| 构建审查任务队列             | `services/review_task_builder.py` + `pipeline.py`                                      | ✅   | 回填、`empty_policy`、anchor、limit                                                                                                                                                                                                                |
| 迭代器并发审查              | `core/pipeline.py`                                                                     | ✅   | `REVIEW_TASK_MAX_WORKERS`（默认 10）与规则拆分共同决定并发形态；与某一固定 Dify 画布实例的任务条数可能因规则 JSON 不同而有数值差异，属数据差异而非能力缺失                                                                                                                                         |
| 审查（LLM）              | `services/llm_engine.py`                                                               | ✅   | 超时、SSL、`degraded` 可计数                                                                                                                                                                                                                         |
| 审查后处理链               | `services/llm_cleaner.py`                                                              | ✅   | think / 围栏 / JSON                                                                                                                                                                                                                             |
| 输出数据格式校验             | `services/output_transform.py`                                                         | ✅   | 4/7 键、`normalize_review_issues`                                                                                                                                                                                                               |
| 构建待审文本库（合流）          | `services/result_merge.py`                                                             | ✅   | 同键 `\n` 拼接；`contract_type` 入参强制                                                                                                                                                                                                               |
| 审查聚合器                | `services/result_merge.py`                                                             | ✅   | 去重、排序；`summary.error_collection`（含 `source`：llm_subtask / document_fetch / field_refine）承载基础设施降级项（与 `final_output` 分离）；`aggregation_*_count`                                                                                                                                                     |
| 最终输出 / 渲染            | `services/report_render.py`                                                            | ✅   | Markdown 含字段、全量 issues、**error_collection**、耗时与任务统计                                                                                                                                                                                           |
| 验收矩阵                 | `docs/DIFY_ACCEPTANCE_MATRIX.md`                                                       | ✅   | 可逐项对照                                                                                                                                                                                                                                         |


## 部署侧说明（非代码缺口）

1. **具体合同平台的 OAuth / 自定义签名字段**：在 API 网关或反向代理完成令牌注入；或使用 `CONTRACT_DOCUMENT_HTTP_HEADERS` / **签名头**（本仓库提供 POST body **HMAC-SHA256** 钩子）。详见 `docs/DEPLOYMENT.md`「OAuth 与网关门面」。
2. **与某一线上 Dify 应用的输出字节级一致**：需同一规则 JSON + 同一模型与温度 + golden 合同样本回归；本仓库提供等价能力与验收矩阵，不内置某一租户画布快照。

## 剩余差距与建议（当前）


| 优先级 | 项 | 说明 |
| --- | --- | --- |
| 低 | 验收矩阵中的「部分」行 | 见 `docs/DIFY_ACCEPTANCE_MATRIX.md`：与具体 SaaS 路径、合同样本、模型输出有关，需在客户环境用真实数据复核，非主链缺能力。 |
| 低 | Golden 覆盖范围 | 仓库内为脱敏短样本 + 上下界断言；与 Dify 画布逐节点字节级对齐需自建数据集与同一模型。 |
| 低 | OAuth 与多租户令牌 | 由网关注入到 `CONTRACT_DOCUMENT_HTTP_HEADERS` 或 sidecar；本仓库不内置某一厂商 OAuth 流程。 |


