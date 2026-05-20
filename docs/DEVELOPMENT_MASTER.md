# 合同审查独立服务 — 开发与阶段总览

> 原始蓝图：`DEVELOPMENT_PLAN.md`（SSL、清洗、切片、并发、文件解析等）。  
> Dify 对照：`docs/workflow_full_backup.md`、`docs/WORKFLOW_TO_API.md`、`docs/DIFY_GAP_ANALYSIS.md`、`docs/DIFY_ACCEPTANCE_MATRIX.md`。

## 阶段文档索引

| 阶段 | 文档 | 要点 |
|------|------|------|
| 基线 | `DEVELOPMENT_PLAN.md` | FastAPI 主链、测试、SSL、llm_cleaner、output_transform、chunk_tasks、并发、docx/pdf |
| 三 | `DEVELOPMENT_PLAN_PHASE3.md` | 远程 id、DocumentProvider、input_warnings |
| 四–五 | `DEVELOPMENT_PLAN_PHASE4.md`、`DEVELOPMENT_PLAN_PHASE5.md` | HTTP 取数、并发、JSON 路径、Header |
| 六 | `DEVELOPMENT_PLAN_PHASE6.md` | 来源库、精提、附件 markdown、聚合、差距文档 |
| 七–九 | `DEVELOPMENT_PLAN_PHASE7.md` … `PHASE9.md` | 精提分段、并行、换行软切 |
| 十–十二 | `DEVELOPMENT_PLAN_PHASE10.md` … `PHASE12.md` | 待审字段库、§5.1 任务拆分、来源预览 |
| 十三 | `DEVELOPMENT_PLAN_PHASE13.md` | 工作流入参 src_1/src_4、预算、报告 Markdown、主文档汇总 |
| 十四 | `DEVELOPMENT_PLAN_PHASE14.md` | 1:1 补强：正式审查可选 §5.1 任务列表、Markdown 类目白名单、HTTP POST 拉取 |
| 十五 | `DEVELOPMENT_PLAN_PHASE15.md` | 主链 closure：精提标题级分块、error_collection、报告与 HTTP 签名 |
| 十六 | `DEVELOPMENT_PLAN_PHASE16.md` | CI（py3.11 + node20）、dry-run 前端、golden 回归、`DEPLOYMENT.md`、`error_collection.source` |
| 十七 | `DEVELOPMENT_PLAN_PHASE17.md` | Golden 扩展（Markdown 行级样本）、主文档排期表述与能力现状对齐 |
| 十八 | `DEVELOPMENT_PLAN_PHASE18.md` | 三合一 v1.4：`mode_0` 代码提取、待审文本库2 合流、字段切片重叠、`format_index_ranges` |

## 运行与验证

```bash
python3 -m pytest tests/ -v
uvicorn contract_review_api.main:app --reload --port 8000
```

前端（可选）：`frontend/` 内 `npm run dev`（见 `README.md`）。

CI：任意分支 `push` 或向 `main` 提 PR 时，`.github/workflows/ci.yml` 运行 **pytest**（Python 3.11，`LLM_MODE=stub`）与 **前端 `npm ci` + `npm run build`**（Node 20）。

## 后续可排期方向

- HTTP 生产鉴权（签名 / OAuth / POST；参见 `docs/DEPLOYMENT.md`「OAuth 与网关门面」）  
- 精提与 Dify 数值对齐：扩充 **golden** 数据集、固定模型与温度做回归对比（`FIELD_REFINE_CHUNK_STRATEGY=markdown_heading` 等已具备）  
- 与 Dify 画布逐节点自动化 diff 流水线（需规则 JSON 与合同样本库）  
