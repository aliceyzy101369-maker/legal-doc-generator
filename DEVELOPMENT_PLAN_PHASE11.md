# 第十一阶段：工作流 §5.1「字段提取任务」可观测（方案定稿）

## 选定方案（最佳实践）

| 场景 | 暴露内容 | 理由 |
|------|-----------|------|
| **`POST /reviews/dry-run`** | 完整 **`field_extraction_tasks`**：`{ "mode_1": [...], "mode_23": [...] }`（与待审字段库行结构一致） | 对账、调试、替代 Dify 画布「构建字段提取任务」节点；与已有 `source_library` / `pending_object_field_library` 同屏 |
| **`POST /reviews`（正式）** | 仅 **`field_extraction_task_counts`**：`{ "mode_1": n, "mode_23": m }` | 避免在每次审查响应中重复大块 JSON；集成方需要明细时先调 dry-run |

## 交付

- `contract_review_api/services/field_extraction_tasks.py`：`build_field_extraction_task_split`  
  - `mode == 1` → `mode_1`；`mode in {2,3,23}` → `mode_23`；其余数字 → `mode_1`（兼容仅写 `mode:1` 的规则集）。  
- `pipeline`：state 挂载 `field_extraction_tasks`；dry-run `summary` 全量 + `field_extraction_task_counts`；正式 `summary` 仅 counts。  
- 测试：`tests/test_field_extraction_tasks.py`；pipeline / integration / observability 断言扩展。  

## 未做

- 任务对象内再嵌入 **`src -> content` 映射**（工作流脚本在 §5.1 内拼接）；当前仍以 `review_tasks` + 主链为准。  
