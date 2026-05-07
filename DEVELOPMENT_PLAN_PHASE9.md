# 第九阶段：精提分段软切分（换行优先）

## 交付

1. **`FIELD_REFINE_CHUNK_SOFT_BREAK`**（默认 **true**）  
   - 在每个块的硬上限前，于 **`FIELD_REFINE_CHUNK_BREAK_WINDOW`**（未设 env 时取 `max(120, min(chunk_size//5, 2000))`，且可被 env 覆盖并 clamp 到 `[32, chunk_size]`）内向 **后** 查找最后一个 `\n`，若切出的段长度 ≥ `chunk_size//8` 则在该行尾断开；否则仍按固定步长硬切。  
   - **`false`**：与第七阶段相同的纯按字符步长切分。  

2. **实现**  
   - `_chunk_text_for_field_refine` 内联软切分；`_chunk_text_hard` 保留为硬切分路径。  

3. **测试**  
   - 换行优先、关闭软切分与硬切一致；原固定步长用例在 `FIELD_REFINE_CHUNK_SOFT_BREAK=false` 下运行。  

4. **文档**  
   - `.env.example`、`README`、`docs/DIFY_GAP_ANALYSIS.md`、`docs/DIFY_ACCEPTANCE_MATRIX.md`。  

## 未做

- 按 **Markdown 标题 / 空行段落** 的语义切片；双语种换行符以外的边界规则。  
