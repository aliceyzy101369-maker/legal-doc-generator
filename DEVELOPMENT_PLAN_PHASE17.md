# 第十七阶段 — Golden 扩展与矩阵/主文档跟进

## 目标

在第十六阶段 CI 与 stub golden 基础上，**扩大脱敏 golden 覆盖**（含 Dify 行级 `pid##category##text` 输入），并同步主文档中已过时的「排期」表述。

## 交付

1. **`tests/fixtures/golden/sample_markdown_lines.json`**：行级 markdown 合同样本 + `expect.input_parse_mode` / `markdown_line_count_min` 等范围断言。
2. **`tests/test_golden_regression.py`**：对可选字段 `input_parse_mode`、`markdown_line_count_min` 做断言（仍不全文比对模型输出）。
3. **`docs/DEVELOPMENT_MASTER.md`**：阶段索引增加第十七行；「后续可排期」与精提 Markdown 标题策略现状对齐。

## 未做项

- 与 Dify 画布逐节点、同模型下的字节级对比数据集（需客户侧样本与规则快照）。

## 验证

```bash
python3 -m pytest tests/ -q
```
