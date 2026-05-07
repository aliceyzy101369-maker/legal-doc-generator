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

## 运行与验证

```bash
python3 -m pytest tests/ -v
uvicorn contract_review_api.main:app --reload --port 8000
```

前端（可选）：`frontend/` 内 `npm run dev`（见 `README.md`）。

## 后续可排期方向

- HTTP 生产鉴权（签名 / OAuth / POST）  
- 精提切片：Markdown 标题级边界  
- 与 Dify 画布逐节点 golden 对比数据集  
