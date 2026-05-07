# 第十三阶段：工作流入参补全 + 文档总表 + 报告增强

## 交付

1. **`ReviewCreateRequest`（对齐 workflow §2.2）**  
   - `contract_subject` → 来源库 **src=1**  
   - `business_info` + `enterprise_list`（合并）→ **src=4**  
   - `resolved_src4_business_slot()`  

2. **`assemble_source_inputs` / `build_source_library`**  
   - Pipeline 组装时传入上述字段。  

3. **输入预算**  
   - `estimate_input_budget(..., extra_chars=)` 计入主体与工商槽位字符，防超大绕过。  

4. **可观测性**  
   - `summary.source_slot_lens`：`src1_contract_subject`、`src4_business_slot` 长度（review + dry-run）。  

5. **`POST /reviews/upload`**  
   - Form：`contract_subject`、`business_info`、`enterprise_list`（可选）。  

6. **`render_markdown`**  
   - 中文标题与结构；可选 `final_comment_count` / `extracted_info_count`。  

7. **文档**  
   - `docs/WORKFLOW_TO_API.md`：节点 → API 总表  
   - `docs/DEVELOPMENT_MASTER.md`：阶段索引与后续方向  
   - `README`、`.env.example`、`DIFY_GAP_ANALYSIS` 同步  

8. **测试**  
   - `tests/test_workflow_dify_inputs.py`  
