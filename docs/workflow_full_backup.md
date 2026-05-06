# 合同审查工作流完整备份（程序化迁移版）

## 1. 总流程（端到端）

`开始`
-> `调取入参内容`
-> 分支A（主合同）+ 分支B（附件）
-> `构建字段取值来源库`
-> `获取审查规则集` -> `提取工作流审查规则集` -> `构建待审对象字段库`
-> `构建字段提取任务`
-> 粗提分支（段落编号 -> 回填字段值）
-> 精提+判断分支（直接提字段值）
-> `构建待审文本库`
-> `构建审查任务队列` -> `迭代器` -> `审查(LLM)`
-> `审查结果处理` -> `清洗` -> `输出数据格式校验` -> `revised_text检验`
-> `审查聚合器`
-> `最终输出处理`
-> `结果渲染任务`

---

## 2. 入参与前置节点

### 2.1 开始

- 类型：开始节点
- 输入：用户输入 `input`

### 2.2 调取入参内容（脚本）

- 从 `params.input`（JSON 字符串）提取：
  - `contract_content`
  - `ruleset_id`
  - `contract_type`
  - `enterprise_list`（转 JSON 字符串）
  - `annex_list`（提取 id 列表，输出 string 列表）
  - `business_info`（转 JSON 字符串）

---

## 3. 文本获取分支

### 3.1 分支A（主合同）

1. `获取合同文本`（工具/API）
  - 入参：`id:number`
  - 出参：`data`（含 `textContent/jsonContent/systemSuccess/systemErrorCode/systemErrorMsg`）
2. `获取主合同和附件的markdow`（脚本）
  - 入参：`jsonContent + name`
  - 出参：markdown 文本（`# 标题` + `pid##category##text`）
  - 过滤：`category == "nuber"`（历史拼写）

### 3.2 分支B（附件）

1. `迭代器`
  - 集合：附件 id 列表（`LIST<String>`）
  - 并发：10
  - 忽略迭代异常：开
2. `附件 id 值转为number 类型`（脚本）
  - 数字字符串 -> `int`
  - 非法 -> `None`
3. `获取附件文本`（工具/API）
  - 入参：`id:number`
  - 出参：同主合同结构
4. `获取主合同和附件的markdow`（脚本）
  - 与 A 支同构
  - 过滤：`category == "number"`
5. `附件内容聚合器`
  - 输出：`aggregateCollection`、`errorIteratorCollection`
6. `附件内容合并`（脚本）
  - 将附件 markdown 以 `\n\n` 拼接为单文本

---

## 4. 来源库与规则库

### 4.1 构建字段取值来源库（脚本）

- 输入：
  - `src_1` 合同主体
  - `src_2` 主合同正文
  - `src_3` 合同附件（合并后）
  - `src_4` 工商信息
- 输出（JSON 字符串）：

```json
[
  {"src": 1, "content": "..."},
  {"src": 2, "content": "..."},
  {"src": 3, "content": "..."},
  {"src": 4, "content": "..."}
]
```

### 4.2 获取审查规则集（工具/API）

- 入参：`rulesetIds: LIST<String>`
- 出参：`code/msg/data/systemSuccess/systemErrorCode/systemErrorMsg`

### 4.3 提取工作流审查规则集（脚本）

- 逻辑：展开 `data[*].rules`，过滤非对象，输出扁平规则列表（JSON 字符串）

### 4.4 构建待审对象字段库（脚本）

- 遍历规则 `target_fields`
- 过滤：
  - 非对象字段
  - `name` 为空
  - `src == 0` 或 `mode == 0`
- 按 `name` 去重
- 输出：待审字段库（JSON 字符串）

---

## 5. 字段提取任务构建

### 5.1 构建字段提取任务（脚本）

- 输入：
  - `fields`（待审字段库）
  - `src_list`（取值来源库）
- 逻辑：
  - 容错解析字符串 JSON / list
  - 构建 `src -> content` 映射（同 src 可拼接）
  - 生成两类任务：
    - `mode_1`：粗提任务
    - `mode_23`：精提+判断任务
- 输出：
  - `mode_1: LIST<Object>`
  - `mode_23: LIST<Object>`

---

## 6. 粗提链路（mode_1）

1. `粗提切片`（脚本，limit=8000）
  - 长文本分片，支持 JSON list / Markdown 两种来源
2. `迭代-提取粗提字段值`
  - 并发 5，忽略异常
3. `LLM大模型提取字段值的段落编号`
  - 输出：`{字段名: [段落编号...]}`（JSON）
4. `大模型结果处理`
  - 去 `</think>` 前缀
5. `数据清洗`
  - 去 markdown 围栏
6. `json结构检查`
  - JSON 容错解析
  - 仅保留 `str -> list` 结构
7. `提取粗提字段值`
  - 按段落编号回填字段内容
  - 输出：`[{review_target_field, review_target_content}]`
8. `粗提聚合器`
  - 汇总粗提结果

---

## 7. 精提+判断链路（mode_23）

1. `精提+判断切片`（脚本，limit=8000）
  - 与粗提切片同构
2. `迭代-提取精提+判断字段值`
  - 并发 5，忽略异常
3. `LLM大模型提取字段值`
  - 直接输出字段值列表
4. `大模型结果处理`
  - 去 `</think>`
5. `数据清洗`
  - 去围栏 + 结构归一 + fallback
6. `精提+判断聚合器`
  - 汇总精提结果

---

## 8. 合流与审查执行

### 8.1 构建待审文本库（脚本）

- 输入：粗提聚合 + 精提聚合 + `contract_type`
- 逻辑：
  - 强容错解析（含字符串化 JSON 列表/对象）
  - 同字段内容按顺序拼接
  - 强制重写“合同类型”字段（删旧加新）
- 输出：统一待审文本库（JSON 字符串）

### 8.2 构建审查任务队列（脚本：`execute_review_tasks`）

- 输入：`fields` + `rules` + `limit=7000`
- 逻辑：
  - 字段内容回填规则 `target_fields.content`
  - `src==0` 或 `mode==0` 使用 `desc` 兜底
  - `empty_policy==1` 且全空规则跳过
  - 规则按长度分组
  - 基于 `src=0` 的 anchor 做不可拆分预分组（`title == anchor_name`）
  - 输出任务：
    - `待审文本`
    - `审查规则`

### 8.3 迭代器（审查任务）

- 输入：`构建审查任务队列.output`
- 并发：10
- 忽略异常：开

### 8.4 审查（LLM）

- 输入：单个任务对象
- 输出：审查意见数组（问题项）

### 8.5 审查后处理链

1. `审查结果处理`：去 `</think>`
2. `清洗`：去代码围栏
3. `输出数据格式校验`：结构规范化（4 键/7 键）、`category/original_id` 等强校验与修正
4. `revised_text检验`：
  - 统一字符串化
  - 去掉 `*`/`_`
  - 去掉 `数字##英文##` 前缀
5. `审查聚合器`：汇总审查结果

---

## 9. 最终输出

### 9.1 最终输出处理（脚本）

- 输入：
  - `input_1`：审查聚合结果（多条字符串化 JSON）
  - `input_2`：待审文本库
- 输出对象：

```json
{
  "comment_list": [...],
  "extracted_info": [...]
}
```

- 其中：
  - `comment_list`：解析 `input_1` 得到
  - `extracted_info`：由 `review_target_field/content` 映射为 `title/comment`，并清理段落前缀

### 9.2 结果渲染任务

- Content 来源：`最终输出处理.output`
- MetaData：空
- 作为工作流终点输出

---

## 10. 已识别稳定性风险（迁移时重点保留/修复）

1. 并发链路重复触发导致聚合抖动
2. 上下游混用“字符串化 JSON 数组”与对象结构
3. A/B 分支过滤词不一致（`nuber` vs `number`）
4. LLM 输出对后处理链依赖很强（`</think>`、围栏、结构校验缺一不可）

---

## 11. 程序化迁移建议（简版）

1. 将“切片逻辑”抽成通用函数（粗提/精提复用）
2. 所有 LLM 输出统一走标准清洗与结构校验管道
3. 合流节点保留“合同类型强覆盖”逻辑
4. 聚合层保留 `success/error` 双集合，便于审计与回溯
5. 仅在 API 边界使用 JSON 字符串，内部尽量传对象结构

