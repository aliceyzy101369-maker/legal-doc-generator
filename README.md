# Legal Doc Generator ⚖️

基于 Streamlit 的法律文书自动生成系统，支持一键生成委托代理协议、授权委托书、民事出庭函、法定代表人身份证明书等全套法律文书。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red)
![License](https://img.shields.io/badge/License-MIT-green)

## 功能特点

- 📝 **多文书类型**：委托代理协议、授权委托书、民事出庭函、法定代表人身份证明书
- 👔 **律师团队信息**：支持主办律师、辅办律师信息配置
- 🏢 **委托方信息**：支持自然人和公司法人两种类型
- 📋 **对方当事人**：支持多个对方当事人
- 💰 **代理费条款**：支持固定收费、风险代理、固定+风险三种模式
- 📜 **代理权限**：一般代理/特别授权（含预置权限项）
- 🎨 **美观 UI**：专业法律风格界面，深蓝色侧边栏

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/<你的用户名>/legal-doc-generator.git
cd legal-doc-generator
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 或 .venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置律所信息

```bash
cp config.example.json config.json
# 编辑 config.json，填入你的律所信息
```

### 5. 准备 Word 模板

将你的 Word 模板文件（.docx）放入 `templates/` 目录，支持 Jinja2 语法占位符如 `{{委托人}}`、`{{案由}}` 等。

### 6. 运行

```bash
streamlit run generate_docs.py
```

## 项目结构

```
legal-doc-generator/
├── generate_docs.py      # 主程序（Streamlit Web 应用）
├── setup_templates.py     # 模板预处理脚本
├── config.example.json   # 配置示例文件
├── templates/            # Word 模板目录（不含）
├── output/              # 生成的文书输出目录（不含）
└── .gitignore           # Git 忽略配置
```

## 配置说明

编辑 `config.json`：

```json
{
    "firm_name": "你的律所名称",
    "firm_address": "律所地址",
    "main_lawyer": "主办律师姓名",
    "lawyer_phone": "律师联系电话",
    "second_lawyer": "辅办律师（可选）"
}
```

## 使用流程

1. 在侧边栏查看律所信息
2. 填写委托方信息（自然人/公司）
3. 填写对方当事人信息
4. 填写律师团队信息
5. 填写案件核心信息（案由、审理程序、争议金额等）
6. 选择诉讼地位和代理权限
7. 配置代理费条款
8. 点击「生成全套法律文书」

## 技术栈

- **Python 3.10+**
- **Streamlit** - Web 框架
- **python-docx-template** - Word 文档生成

## 注意事项

- ⚠️ 请勿将含真实当事人信息的文件提交到 Git
- 📁 生成的文书保存在 `output/` 目录
- 📋 首次使用需准备符合规范的 Word 模板

## 许可证

MIT License

---

欢迎 Star ⭐️ 和贡献！
