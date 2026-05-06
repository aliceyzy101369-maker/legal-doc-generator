# 第六阶段：补齐 Dify 核心差距 — 自主执行计划

> **执行方式**：从头到尾自主执行，遇到问题自己修，不要停下来问用户。
> 每完成一个任务跑 `python3 -m pytest tests/ -v`，失败就自行修复直到全绿。
> 全部完成后给用户一份总结报告。

> **补充约束（必须遵守）**：
> 1. 所有新增测试强制 stub 模式（`LLM_MODE=stub`），不依赖真实 API
> 2. logging 不记录合同全文、API Key、完整模型返回；只记录长度/数量/状态
> 3. 不要新增计划外功能（不加前端、不加新接口、不加 npm/React）
> 4. 不删除或重写已通过的代码和测试，只做增量修改
> 5. Git 提交前确认 .env 未被追踪

---

## 当前状态

- 80 个测试通过
- 主链已跑通（stub + real 模式）
- 差距集中在 3 个区域（见 docs/DIFY_GAP_ANALYSIS.md）

---

## 任务 1：构建字段取值来源库（当前标记 ❌）

> 对应 Dify 节点：「构建字段取值来源库」
> 这是当前唯一标记 ❌ 的核心节点

### 要做什么

创建 `contract_review_api/services/source_library.py`，实现：

```python
def build_source_library(
    contract_subject: str,    # 合同主体信息（src=1）
    main_contract: str,       # 主合同正文 markdown（src=2）
    annexes: str,             # 附件合并文本（src=3）
    business_info: str        # 工商信息（src=4）
) -> list[dict]:
    """
    构建字段取值来源库，输出格式：
    [
        {"src": 1, "content": contract_subject},
        {"src": 2, "content": main_contract},
        {"src": 3, "content": annexes},
        {"src": 4, "content": business_info}
    ]
    空字符串的来源也要保留（content 为空串），不要过滤掉。
    """
```

### 接入主链

在 `pipeline.py` 中调用 `build_source_library`：
- 从已有的入参和文本处理结果中组装 4 个来源
- 如果某个来源不存在（比如没有附件、没有工商信息），传空字符串
- 把来源库传给后续的字段提取和审查任务构建

### 测试

创建 `tests/test_source_library.py`：
- 4 个来源都有内容时，输出 4 项，src 编号正确
- 部分来源为空时，仍输出 4 项（content 为空串）
- 空调用（全空）时，仍输出 4 项

---

## 任务 2：精提链路对齐（当前标记 ⚠️）

> 对应 Dify 节点：粗提/精提双链路中的 mode_23
> 差距分析原文："精提以规则占位为主，不等价 mode_23"

### 要做什么

在 `field_extraction.py` 或新建 `field_refine.py` 中，确保精提链路具备以下能力：

1. **精提任务构建**：
   - 输入：字段列表 + 取值来源库
   - 按字段的 mode 分流：mode=1 走粗提（段落编号定位），mode=2/3 走精提（直接提取值）
   - 如果当前代码没有 mode 概念，就简化为：所有字段统一走"直接 LLM 提取值"

2. **精提 LLM 调用**（stub 模式下用模拟返回）：
   - 输入：字段名 + 取值来源文本
   - 输出：`[{"review_target_field": "甲方", "review_target_content": "北京甲公司"}]`
   - 用 `llm_cleaner.clean_llm_output` 清洗返回

3. **精提结果合并到主链**：
   - 精提结果和现有正则提取结果合并
   - 同字段名的内容用 `\n` 拼接（不覆盖）
   - 合并后的结果传给审查任务构建

### 接入主链

在 `pipeline.py` 中：
- 正则提取后，如果 `FIELD_REFINE_MODE=llm`（环境变量），追加一轮 LLM 精提
- 精提结果与正则结果合并
- 默认 `FIELD_REFINE_MODE=regex`（只走正则，行为不变）

### 测试

在 `tests/test_field_refine.py` 中：
- stub 模式下精提返回结构正确
- 精提结果能与正则结果合并
- `FIELD_REFINE_MODE=regex` 时不触发 LLM 调用

---

## 任务 3：附件 markdown 兼容（当前标记 ⚠️）

> 差距分析原文："未复刻附件分支过滤词差异（nuber vs number）"

### 要做什么

在 `text_processing.py` 或 `markdown_line_parser.py` 中：

1. 找到解析 `pid##category##text` 行格式的代码
2. 确认过滤 category 时，兼容 `"nuber"` 和 `"number"` 两种拼写
3. 具体实现：过滤条件改为 `category.lower().strip() in {"number", "nuber"}`

### 测试

在现有测试文件中增加：
- 包含 `"nuber"` category 的行能被正确过滤
- 包含 `"number"` category 的行能被正确过滤
- 大小写混合（如 `"Number"`）也能被过滤

---

## 任务 4：审查聚合器完善（当前标记 ⚠️）

> 差距分析原文："哈希去重 + 严重度排序；与 Dify 多分支聚合仍可能不一致"

### 要做什么

在 `result_merge.py` 中确认或补充：

1. **去重逻辑**：按 `title + comment` 哈希去重（如果已实现就保留）
2. **排序逻辑**：按 degree 排序（高 > 中 > 低），同级按 title 排序
3. **成功/失败分流**：
   - 正常审查结果进入 `aggregateCollection`
   - 降级提示（title 包含"降级"）进入 `errorCollection`
   - `summary` 中体现 `success_count` 和 `error_count`

### 测试

补充测试（如果还没有）：
- 重复的审查意见能被去重
- 结果按严重度排序
- 降级提示不混入正式结果

---

## 任务 5：更新差距分析文档

重新检查所有代码，更新 `docs/DIFY_GAP_ANALYSIS.md`：
- 任务 1-4 完成后，对应的 ❌ 和 ⚠️ 应该变成 ✅ 或更接近 ✅
- 诚实标注仍然存在的差距
- 在文档末尾增加一节"剩余差距与建议"，列出还需要做什么

---

## 任务 6：最终验证 + Git 提交

1. `python3 -m pytest tests/ -v` — 全部通过
2. 确认 `.env` 未被 git 追踪：`git ls-files .env` 应无输出
3. `git add -A && git commit -m "phase6: 补齐来源库、精提链路、附件兼容、聚合完善"`

---

## 完成后输出

给用户一份总结报告，包含：
1. 每个任务的完成情况（逐项列出改了哪些文件）
2. 最终测试总数和通过情况
3. `DIFY_GAP_ANALYSIS.md` 中剩余的 ⚠️ 和 ❌ 项
4. 你认为距离"可替代 Dify 工作流"还差什么（按优先级列 top 3）
5. Git 提交哈希
