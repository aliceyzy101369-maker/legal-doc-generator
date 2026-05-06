# 第六阶段：精提 LLM（Dify mode_23 对齐）

## 目标

- 将 **精提** 从「合流 + 规则占位」扩展为可选的 **全文语义抽取**，对齐 `docs/workflow_full_backup.md` 中 **mode_23**「LLM 直接输出字段值」的语义。
- 保持默认行为不变：`FIELD_REFINE_MODE=rules`（或缺省）时与第五阶段前一致。

## 行为摘要

| 环节 | 说明 |
|------|------|
| 粗提 | 仍为 `extract_field_candidates_coarse`（正则全量命中），不变。 |
| 精提（rules） | `merge_fields` 合流 + 规则 `target_fields` 名补空占位。 |
| 精提（llm） | 以 **完整合同正文**（`pipeline` 传入的 `base_text`，受 `FIELD_REFINE_TEXT_LIMIT` 截断）+ **待抽字段列表**（规则 `target_fields.name` ∪ `FIELD_PATTERNS` 标准键）调用 `run_llm_field_extraction`；解析 JSON 对象后 **非空 LLM 值按字段覆盖** 粗提合并结果，再对规则字段做占位补全，最后 `merge_fields(..., contract_type_override=...)`。 |
| Stub | `LLM_MODE=stub` 时精提 LLM **不发起 HTTP**，等价于本次 LLM 抽取为空，回退为粗提 + 占位。 |

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `FIELD_REFINE_MODE` | `rules` | `llm` / `mode_23` / `mode23` 开启 LLM 精提。 |
| `LLM_FIELD_REFINE` | 空 | `true` / `1` / `yes` / `on` 时等价于开启 LLM 精提（便于布尔开关）。 |
| `FIELD_REFINE_TEXT_LIMIT` | `120000` | 送入抽取模型的最大字符数；超出截断并产生 `llm_field_refine_text_truncated`。 |
| `FIELD_REFINE_LLM_TIMEOUT` | `120` | 抽取请求超时秒数（10–600 夹紧）。 |
| `LLM_MODE` / `LLM_*` | 同审查链路 | `real` 且配置完整时才会调用远程模型。 |

## 与 Dify 仍可能存在的差距

- 未复刻 **精提切片迭代**（画布 limit=8000 多段并发）；当前为 **单次** 全文（截断范围内）抽取。
- 未实现独立 **来源库 JSON**（src_1..4）作为抽取输入；现用合并后的 `base_text`。
- 附件分支 markdown 过滤差异等仍见 `docs/DIFY_GAP_ANALYSIS.md`。

## 涉及文件

- `contract_review_api/services/field_extraction.py` — 模式分支、合并策略、`collect_target_field_names`。
- `contract_review_api/services/llm_engine.py` — `run_llm_field_extraction`、`_field_refine_text_limit`、`_call_real_model` 可选 system 提示。
- `contract_review_api/services/llm_cleaner.py` — `clean_llm_field_json` / `parse_json_object_tolerant`。
- `contract_review_api/core/pipeline.py` — 传入 `contract_text=base_text`。
- `tests/test_field_refine_llm.py`、`tests/test_llm_cleaner.py` — 覆盖合并与 JSON 清洗。
