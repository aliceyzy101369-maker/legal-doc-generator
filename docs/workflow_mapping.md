# Contract Review Workflow Mapping

This document maps the original workflow-node style execution into code modules for the standalone API service.

## Node To Module Mapping

| Workflow Node | Standalone Module | Responsibility |
|---|---|---|
| 调取入参内容 | `services.input_ingest` | Normalize request payload and source metadata |
| 获取合同文本 / 获取主合同和附件markdown | `services.text_processing` | Parse file/text, merge main + attachment content |
| 构建字段提取任务 / 迭代器 | `services.field_extraction` | Build field extraction tasks and candidate values |
| 构建待审对象字段库 | `services.pending_field_library` + `core.pipeline` | Export deduped `target_fields` (excl. src=0 / mode=0) into `summary.pending_object_field_library` |
| 粗提/精提 + 判断 | `services.field_extraction` + `services.rule_engine` | Regex and heuristic extraction with deterministic checks |
| LLM大模型提取字段值 | `services.llm_engine` | Semantic extraction and legal-risk issue generation |
| json结构检查 / 输出数据格式校验 | `api.schemas` + `services.report_render` | Enforce strict response schema |
| 数据清洗 | `services.result_merge` | Normalize text, deduplicate, remove low-value noise |
| 审查结果处理 | `services.result_merge` | Merge rule issues + LLM issues into stable issue list |
| 审查聚合器 / 精提聚合器 / 粗提聚合器 | `services.result_merge` | Empty-guard, idempotent merge, risk sort |
| 最终输出处理 / 结果渲染 | `services.report_render` | JSON + Markdown review report output |

## Faults Observed In Existing Workflow

- Aggregator can run before all branch results are ready.
- Empty aggregate payload (`[]`) can still pass to downstream steps.
- Duplicate fanout execution can repeatedly write the same issues.
- Mixed serialized/non-serialized aggregate payloads degrade stability.

## Guardrails In Standalone Service

1. Empty candidates never overwrite non-empty field values.
2. Result merge is idempotent by deterministic issue key.
3. Output always returns native JSON arrays (no nested stringified arrays).
4. Rule engine and LLM engine produce a common issue schema.
5. Every field and issue contains evidence or explicit missing reason.
