# Dify 工作流 vs 本仓库实现 — 差距分析

> 标注规则（按补充约束）：**仅主链 `pipeline.py` 实际调用的能力可标 ✅**；函数存在但未接入主链标 **⚠️**；未实现标 **❌**。  
> 本文基于 `docs/workflow_full_backup.md`、`docs/workflow_mapping.md` 与当前代码对照整理。

## 总览

| Dify 节点 / 能力 | 主要代码位置 | 状态 | 说明 |
|------------------|-------------|------|------|
| 调取入参内容 | `services/input_ingest.py` + `api/schemas.py` | ✅ | 校验 text/file_path；增加近似输入大小上限；支持可选 `contract_type` 入参 |
| 获取合同文本 / 附件 markdown | `services/text_processing.py` | ⚠️ | 支持主文件+附件本地路径与分段；**未实现** Dify 远程 `id:number` 拉取与 `pid##category##text` 行级格式、历史拼写 `nuber` 过滤 |
| 构建字段取值来源库（src_1..4） | — | ❌ | 当前无独立“来源库”JSON结构；段落带 `doc_type` 元信息但未暴露为 Dify 同款结构 |
| 获取审查规则集 / 展开 rules | `services/ruleset_loader.py` | ✅ | 支持内置+文件 ruleset；未知 id 报错 |
| 构建待审对象字段库 | `services/review_task_builder.py`（部分） | ⚠️ | 规则 `target_fields` 回填在 `build_review_tasks` 内完成；无单独“字段库”JSON产物 |
| 构建字段提取任务（mode_1 / mode_23） | `services/field_extraction.py` | ⚠️ | 当前为单路径正则提取；**未实现** Dify 粗提/精提双模式任务对象与分支 |
| 粗提/精提切片（limit=8000） | `services/text_processing.py` + `core/pipeline.py` | ✅ | `chunk_tasks` 在 `build_review_tasks` **之后**、LLM 调用之前对 `review_tasks` 切片 |
| 构建审查任务队列 | `services/review_task_builder.py` + `pipeline.py` | ✅ | `empty_policy`、`anchor(src=0)`、长度分组、字段回填均在主链使用 |
| 迭代器并发审查 | `core/pipeline.py` | ⚠️ | 使用 `ThreadPoolExecutor(max_workers=5)`；Dify 为并发 10；子任务异常降级为 `模型审查降级提示` |
| 审查（LLM） | `services/llm_engine.py` | ✅ | `urllib` 调用 + `SSL_CERT_FILE`；超时默认 120s；失败降级不抛到 API 层 |
| 审查后处理链（think/围栏/JSON） | `services/llm_cleaner.py` | ✅ | `clean_llm_output` 串联三步；并对“dict 包 list”的常见外层结构做容错 |
| 输出数据格式校验 / revised_text | `services/output_transform.py` | ✅ | `build_final_output` + `normalize_review_issues` |
| 构建待审文本库（同字段拼接 + contract_type 强制） | `services/result_merge.py` + `pipeline.py` | ✅ | `merge_fields`：同 `field_key` 用 `\n` 拼接；`contract_type` 入参覆盖 |
| 审查聚合器 | `services/result_merge.py` | ⚠️ | `merge_issues` 为哈希去重+严重度排序；与 Dify “多条字符串化 JSON 聚合”细节可能不一致 |
| 最终输出 / 渲染 | `services/report_render.py` | ⚠️ | Markdown 报告较简；未完全对齐 Dify 最终节点元数据 |

## 仍建议优先补齐的方向（❌/⚠️ 集中区）

1. **远程合同/附件获取**：与 Dify 工具节点一致的 id 拉取、markdown 行格式与过滤词兼容。  
2. **粗提/精提双链路**：mode_1 / mode_23 任务拆分与字段回填策略。  
3. **聚合语义对齐**：多分支、字符串化 JSON、重复 fanout 的去重策略与 Dify 对齐验证。
