# 合同审查程序 — 完整开发计划

> 这份文件是项目的完整开发指南。请 AI 编程助手（Cursor）阅读本文件后，
> 理解项目背景、当前进度、以及后续所有待完成任务，然后逐步推进实现。

---

## 一、项目背景

### 目标
把一套在 Dify 上运行的"合同审查工作流"，转化为独立可运行的 Python 后端 API 服务（FastAPI），
不再依赖 Dify 画布节点来执行。

### 核心能力
1. 接收合同文本（纯文本或文件）
2. 从合同中提取关键字段（甲方、乙方、项目名称、合同期限等）
3. 加载审查规则
4. 调用大模型（DeepSeek）按规则审查合同
5. 清洗大模型的不稳定输出，转成标准化结构
6. 输出结构化结果：`comment_list`（审查意见）+ `extracted_info`（提取信息）

### 技术栈
- Python + FastAPI
- DeepSeek API（OpenAI 兼容格式，/v1/chat/completions）
- httpx（HTTP 客户端）
- python-dotenv（环境变量管理）
- pytest（测试）

---

## 二、当前项目状态（已完成）

### 项目路径
`/Users/alice/my-first-project`

### 已有模块（全部可用，20 个测试全部通过）

| 文件 | 功能 | 对应 Dify 节点 |
|------|------|---------------|
| `main.py` | FastAPI 入口，POST /reviews、GET /rulesets、POST /reviews/dry-run | 调取入参内容 |
| `core/pipeline.py` | 主流程编排（串联所有步骤） | 整条主链 |
| `core/models.py` | 数据模型定义 | — |
| `services/text_processing.py` | 合同文本分段处理 | 获取合同文本 |
| `services/field_extraction.py` | 用正则提取关键字段 | 构建字段提取任务 |
| `services/ruleset_loader.py` | 从 JSON 文件加载审查规则 | 获取审查规则集 |
| `services/review_task_builder.py` | 把字段+规则组装成审查任务包 | 构建审查任务队列 |
| `services/llm_engine.py` | 调用 DeepSeek（支持 stub/real 双模式） | 审查（LLM） |
| `services/output_transform.py` | 审查结果标准化（4键/7键约束） | 输出数据格式校验 + revised_text检验 |
| `services/result_merge.py` | 结果合并 | 构建待审文本库 |
| `services/rule_engine.py` | 默认规则构造 | — |
| `services/report_render.py` | 摘要生成 | — |
| `services/input_ingest.py` | 输入处理 | — |
| `storage/repository.py` | 结果持久化 | — |
| `api/schemas.py` | 请求/响应模型定义 | — |

### 已有测试（全部通过）
- `tests/test_llm_engine.py` — 3 个测试（缺 env、非法 JSON、超时）
- `tests/test_output_transform.py` — 3 个测试（category 归一、extracted_info 清洗、4/7 键）
- `tests/test_pipeline.py` — 8 个测试（主链、空输入、文件、ruleset、dry-run 等）
- `tests/test_review_task_builder.py` — 2 个测试（empty_policy、anchor 分组）
- `tests/test_ruleset_loader.py` — 4 个测试（默认回落、文件加载、strict 规则、未知 id）

### 当前卡点
LLM real 模式调用 DeepSeek 时报 SSL 错误：
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```
需要先修复这个问题。

### 环境配置文件 (.env)
```
LLM_MODE=real
LLM_API_KEY=（用户已填写真实 key）
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

---

## 三、立即要做的事（按顺序）

### 任务 1：修复 SSL 证书问题 ⚡️ 最高优先级

**问题**：httpx 调用 DeepSeek API 时因 Mac 上 Python 证书链不完整导致 SSL 验证失败。

**修复方案**：
1. 确保 certifi 已安装：`pip3 install certifi`
2. 在 `.env` 文件末尾追加一行 `SSL_CERT_FILE=`，值为 certifi 的 cacert.pem 路径
   （通过 `python3 -c "import certifi; print(certifi.where())"` 获取）
3. 修改 `contract_review_api/services/llm_engine.py`：
   - 在 httpx 请求中使用 `verify=os.environ.get("SSL_CERT_FILE", True)` 参数
   - 确保 `import os` 在文件顶部
4. 确保 `contract_review_api/main.py` 最开头有：
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

**验证方法**：
1. `python3 -m pytest tests/ -v` — 原有 20 个测试必须全部通过
2. 运行以下代码测试 DeepSeek 连通性：
```python
import os
from dotenv import load_dotenv
load_dotenv('.env', override=True)
import httpx
resp = httpx.post(
    os.getenv('LLM_BASE_URL','') + '/v1/chat/completions',
    headers={'Authorization': 'Bearer ' + os.getenv('LLM_API_KEY','')},
    json={'model': os.getenv('LLM_MODEL','deepseek-chat'),
          'messages': [{'role':'user','content':'说一个字'}], 'max_tokens': 10},
    verify=os.environ.get('SSL_CERT_FILE', True),
    timeout=30
)
print('状态码:', resp.status_code)
print('返回:', resp.text[:200])
```
状态码 200 = 修复成功。

---

### 任务 2：确保真实模型调用主链跑通

修复 SSL 后，运行完整审查流程验证：
```python
import json
from dotenv import load_dotenv
load_dotenv('.env', override=True)
from fastapi.testclient import TestClient
from contract_review_api.main import app
client = TestClient(app)
resp = client.post('/reviews', json={
    'text': '甲方：北京甲公司\n\n乙方：上海乙公司\n\n项目名称：智能采购平台\n\n合同期限：自2026年1月1日至2026年12月31日\n\n付款方式：双方另行协商\n\n违约责任：友好协商解决\n\n争议解决：未约定',
    'ruleset_id': 'base-rules'
})
body = resp.json()
issues = body.get('final_output', {}).get('comment_list', [])
print('状态码:', resp.status_code)
print('审查意见数:', len(issues))
for i in issues:
    print(f'  [{i.get("degree","")}] {i["title"]}: {i["comment"][:80]}')
has_fallback = any('降级' in str(i.get('title','')) for i in issues)
print('结论:', '失败（出现降级提示）' if has_fallback else '成功：真实模型审查通过')
```

**通过标准**：
- 状态码 200
- 审查意见数 > 1
- 不出现"模型审查降级提示"
- 审查意见内容对应合同中的具体问题（付款模糊、违约责任不明确等）

---

### 任务 3：增加 LLM 输出清洗模块（llm_cleaner.py）

> 对应 Dify 节点：「大模型结果处理」+「数据清洗」+「json结构检查」

创建 `contract_review_api/services/llm_cleaner.py`，实现以下函数：

```python
def remove_think_prefix(text: str) -> str:
    """查找 </think>，如果存在则返回其后的文本，否则原样返回。最后 strip()"""

def remove_markdown_fence(text: str) -> str:
    """用正则删除独立行的 ```xxx 和 ```。最后 strip()
    等价：re.sub(r"^```[\\w-]*\\s*$", "", text, flags=re.MULTILINE)
          re.sub(r"^```\\s*$", "", text, flags=re.MULTILINE)"""

def parse_json_tolerant(text: str) -> dict | list:
    """输入为空 → 返回 {}
    先尝试 json.loads(text)
    失败时用正则容错提取 "key": [...] 形式的键值对
    对 dict 结果：仅保留 key 是 str 且 value 是 list 的键值
    返回解析后的 Python 对象"""

def clean_llm_output(raw_text: str) -> dict | list:
    """串联以上 3 步：remove_think_prefix → remove_markdown_fence → parse_json_tolerant
    这是对外的主入口函数"""
```

**如果 llm_engine.py 中已有类似清洗逻辑，请将其抽取到 llm_cleaner.py 中，
并让 llm_engine.py 调用 llm_cleaner 的函数，避免重复代码。**

同时创建 `tests/test_llm_cleaner.py` 覆盖：
- 带 `</think>` 前缀的清洗
- 带 `` ```json `` 围栏的清洗
- 非法 JSON 的容错提取
- 空输入返回 `{}`
- `clean_llm_output` 串联清洗的完整测试

---

### 任务 4：完善审查意见标准化逻辑

> 对应 Dify 节点：「输出数据格式校验」+「revised_text检验」

确认 `output_transform.py` 中的 `normalize_review_issues` 函数已实现以下规则
（如果缺少请补齐）：

- 每个审查意见对象必须有：title, comment, degree, category
- category 强制归一为 0 或 1（其他值回落为 0）
- 当 category=1（条款修订类）时：
  - change_type 只允许 "修订"/"删除"/"新增"，非法值回落为 "新增"
  - original_id 必须是 list，None/空值/脏值回落为 [1]
  - revised_text 清洗：去掉 `*` 和 `_`，去掉 `数字##英文##` 格式前缀（如 `21##text##`）
- 当 category=0（风险提示类）时，只保留 title/comment/degree/category 四个键
- 跳过非 dict 的元素

---

### 任务 5：增加合同文本切片能力

> 对应 Dify 节点：「粗提切片」+「精提+判断切片」

在 `text_processing.py` 中增加（如果还没有）：

```python
def chunk_tasks(tasks: list[dict], limit: int = 8000) -> list[dict]:
    """把任务列表中的超长文本切片，保证每个任务包不超过 limit 字符。
    切片策略：
    1. 如果 "取值来源" 是 JSON list 字符串，按元素切
    2. 如果是 Markdown 文本，先按一级标题 # 切成语义单元，再按行补切
    3. 保留原任务的其他字段不变，只替换 "取值来源"
    4. 粗提和精提共用同一套切片逻辑"""
```

---

### 任务 6：支持审查任务并发执行

> 对应 Dify 节点：「迭代器（并发10）」

修改 `pipeline.py` 中的审查执行部分：
- 使用 `concurrent.futures.ThreadPoolExecutor(max_workers=5)` 并发执行审查任务
- 单个任务失败不阻断整体（等价 Dify 的"忽略迭代中异常"）
- 失败任务记录到 error_list，不混入正式结果
- summary 中增加 `success_count` 和 `error_count`

---

### 任务 7：支持文件上传（docx/pdf 解析）

在 `input_ingest.py` 或新建 `file_parser.py` 中增加：
- 支持 .docx 文件读取（使用 python-docx 库）
- 支持 .pdf 文件读取（使用 PyPDF2 或 pdfplumber 库）
- 把文件内容转成纯文本后，走和 text 输入一样的主链

需要在 `requirements.txt` 中添加对应依赖。

---

## 四、Dify 工作流完整规格（程序化参考）

这一节是 Dify 工作流的完整节点清单，供实现时参考细节逻辑。

### 总体流程
```
开始 → 调取入参内容
→ 分支A（主合同）+ 分支B（附件）
→ 构建字段取值来源库
→ 获取审查规则集 → 提取工作流审查规则集 → 构建待审对象字段库
→ 构建字段提取任务
→ 粗提分支（段落编号定位 → 回填字段值）
→ 精提+判断分支（直接提字段值）
→ 构建待审文本库（合流）
→ 构建审查任务队列 → 迭代器 → 审查(LLM)
→ 审查结果处理 → 清洗 → 输出数据格式校验 → revised_text检验
→ 审查聚合器 → 最终输出处理 → 结果渲染任务
```

### LLM 输出清洗链（三处 LLM 节点共用）
所有 LLM 节点输出都经过相同的清洗链：
1. **去 `</think>` 前缀**：模型可能带思考过程，截取 `</think>` 之后的内容
2. **去 markdown 围栏**：删除 `` ```json `` 和 `` ``` ``
3. **JSON 容错解析**：先 `json.loads`，失败则用正则提取 `"key": [...]`
4. **结构过滤**：仅保留合法键值对

### 审查任务构建核心规则
- **字段回填**：把提取到的字段内容填入规则的 target_fields
- **空策略过滤**：`empty_policy==1` 且所有字段为空时跳过
- **锚点不可拆**：`src=0` 的字段对应的规则必须在同一分组
- **按长度分组**：每组不超过 limit（7000），保证模型输入不超限

### 审查意见输出规范
- **4 键对象**（风险提示，category=0）：title, comment, degree, category
- **7 键对象**（条款修订，category=1）：title, change_type, original_id, revised_text, comment, degree, category
- `change_type` 只允许：修订 / 删除 / 新增
- `original_id` 必须是 list
- `revised_text` 需清洗 `*`、`_` 和 `数字##英文##` 前缀

### 最终输出结构
```json
{
  "comment_list": [
    {"title": "...", "comment": "...", "degree": "高/中/低", "category": 0},
    {"title": "...", "comment": "...", "degree": "...", "category": 1,
     "change_type": "修订", "original_id": [3], "revised_text": "..."}
  ],
  "extracted_info": [
    {"title": "甲方", "comment": "北京甲公司"},
    {"title": "合同期限", "comment": "自2026年1月1日至2026年12月31日"}
  ]
}
```

### 已知风险点
- A/B 分支过滤词不一致（`nuber` vs `number`），程序中需做兼容
- 上下游存在"字符串化 JSON 数组"混用，解析时需容错
- 多处依赖 LLM 清洗链，少一步就会污染下游

---

## 五、验收标准

### 阶段 1 验收（任务 1-2）
- [ ] SSL 修复后 DeepSeek API 返回 200
- [ ] POST /reviews 真实模型返回多条审查意见
- [ ] 不出现"模型审查降级提示"
- [ ] 原有 20 个测试不被破坏

### 阶段 2 验收（任务 3-4）
- [ ] llm_cleaner 测试全部通过
- [ ] 带 `</think>` / 围栏 / 坏 JSON 的输入都能正确清洗
- [ ] category=0 的意见只有 4 个键，category=1 有 7 个键

### 阶段 3 验收（任务 5-7）
- [ ] 超长文本切片后每片不超过 limit
- [ ] 并发审查时单任务失败不崩溃
- [ ] docx/pdf 文件能正确解析并走审查流程

---

## 六、工作方式约定

1. **先修 SSL（任务 1）**，这是当前阻塞项
2. 每完成一个任务，自动运行 `python3 -m pytest tests/ -v` 确认不回归
3. 新功能必须有对应测试
4. 代码风格保持与现有代码一致
5. 不要删除或重写已有的通过的代码，在其基础上增量修改
