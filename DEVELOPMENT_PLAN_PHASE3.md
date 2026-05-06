# 合同审查程序 — 第三阶段自主开发计划（执行摘要）

本文件标记第三阶段已在仓库内落地的主要交付物（完整原始需求见项目对话/规格备份）。

## 已完成（对应计划章节）

1. **基线**：`git status` 清洁（除用户保留的未跟踪文件如 `module01.py`）、`pytest` 全绿。
2. **Dify 输入形态**：`DocumentProvider`（stub / none）、`gather_resolved_contract_bundle`、请求体 id 别名、`input_warnings` 软失败。
3. **Markdown 行**：`markdown_line_parser.py`、主链启发式接入、`dry-run` 的 `markdown_line_records`（无敏感正文）。
4. **粗提/精提**：`extract_field_candidates_coarse` + `refine_field_candidates`、`summary` 计数、粗提空降级提示。
5. **验收矩阵与夹具**：`docs/DIFY_ACCEPTANCE_MATRIX.md`、`tests/fixtures/dify_cases/*.json`、`tests/test_dify_acceptance.py`。
6. **可观测性**：`trace_id`、`llm_call_count`、`degraded_count`、`chunk_count`、`attachment_count` 等。
7. **文档**：`README.md`、`docs/DIFY_GAP_ANALYSIS.md` 更新。

## 刻意未做 / 留待下一阶段

- 绑定某一具体外部合同 SaaS 的 HTTP Provider（避免硬编码平台）。
- Dify 迭代器并发数改为 10（当前 5，行为可测但非 1:1）。
- 与 Dify 完全一致的 LLM 精提提示词与双分支任务对象。
