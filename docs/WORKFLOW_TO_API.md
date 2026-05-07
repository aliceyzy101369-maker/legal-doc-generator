# Dify 工作流备份 → 本 API 对照表

> 依据 `docs/workflow_full_backup.md` 与当前实现整理，便于迁移与验收。

## 总流程节点

| 工作流（备份文档） | HTTP / 代码入口 | 说明 |
|-------------------|-----------------|------|
| 调取入参内容 | `POST /reviews`、`POST /reviews/dry-run`、`POST /reviews/upload` | `ReviewCreateRequest`；含 `contract_subject` / `business_info` / `enterprise_list`（src_1 / src_4） |
| 分支 A/B 合同与附件 | `input_ingest.gather_resolved_contract_bundle` + `document_provider` | 文本 / 路径 / 远程 id |
| 构建字段取值来源库 | `source_library.build_source_library` + `assemble_source_inputs` | 四项 `src=1..4`；dry-run 返回完整 JSON |
| 获取审查规则集 | `ruleset_loader.load_review_rules` | `ruleset_ids` |
| 构建待审对象字段库 | `pending_field_library.build_pending_object_field_library` | `summary.pending_object_field_library` |
| 构建字段提取任务 §5.1 | `field_extraction_tasks.build_field_extraction_task_split` + enrich | dry-run：`field_extraction_tasks`；review：`field_extraction_task_counts` |
| 粗提 / 精提 | `field_extraction` + `llm_engine.run_llm_field_extraction` | 正则 + 可选 LLM；分段见环境变量文档 |
| 构建待审文本库 | `result_merge.merge_fields` | 同键 `\n`；`contract_type` 覆盖 |
| 构建审查任务队列 | `review_task_builder.build_review_tasks` | anchor、`empty_policy`、7000 分组 |
| 粗提/审查切片 | `text_processing.chunk_tasks` | 8000 |
| 迭代器审查 | `pipeline` + `ThreadPoolExecutor` | `REVIEW_TASK_MAX_WORKERS` |
| 审查 LLM | `llm_engine` | stub / real；SSL 见 `SSL_CERT_FILE` |
| 清洗与输出校验 | `llm_cleaner` + `output_transform` | 4/7 键 |
| 审查聚合 | `result_merge.merge_issues` + `partition_issues_for_final_output` | 降级标题分流 |
| 结果渲染 | `report_render.render_markdown` | Markdown 报告正文 |

## 入参别名（远程 id）

| 请求字段 | 含义 |
|----------|------|
| `contract_id` / `main_contract_id` / `file_id` | 主合同远程 id（任一） |
| `attachment_ids` / `file_ids` / `files` | 附件 id 列表 |

## 环境变量索引

见仓库根目录 **`README.md`** 与 **`.env.example`**（LLM、文档 HTTP、精提分段、CORS、审查并发等）。
