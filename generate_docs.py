import streamlit as st
import os
import json
from datetime import datetime
from docxtpl import DocxTemplate


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


config = load_config()

# ---------------------------------------------------------------------------
# Page Config & Global CSS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="法律文书生成系统",
    page_icon="⚖️",
    layout="centered",
)

st.markdown(
    """
    <style>
    :root {
        --accent: #1b3a5c;
    }
    /* Sidebar branding */
    section[data-testid="stSidebar"] {
        background-color: #0e2a47;
    }
    section[data-testid="stSidebar"] * {
        color: #e8ecf1 !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.15);
    }
    /* Hide default Streamlit menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — Firm Branding
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚖️ 律所信息")
    st.divider()

    firm_name = config.get("firm_name", "未配置律所名称")
    firm_address = config.get("firm_address", "")
    main_lawyer_default = config.get("main_lawyer", "")
    lawyer_phone_default = config.get("lawyer_phone", "")

    st.markdown(f"**{firm_name}**")
    if firm_address:
        st.caption(firm_address)

    st.divider()
    st.markdown(f"**主办律师：** {main_lawyer_default}")
    st.markdown(f"**电话：** {lawyer_phone_default}")
    st.divider()
    st.caption("配置来源：config.json")

# ---------------------------------------------------------------------------
# Main Title
# ---------------------------------------------------------------------------
st.markdown("## ⚖️ 法律文书生成系统")
st.caption("填写委托信息后一键生成全套法律文书")
st.divider()

# ===========================================================================
# I. 委托方信息
# ===========================================================================
with st.container(border=True):
    st.markdown("#### 🏢 委托方信息")

    client_type = st.radio(
        "委托方类型",
        ["自然人", "公司/法人"],
        horizontal=True,
        help="选择后将自动调整下方需要填写的字段",
    )

    col_name, col_id = st.columns(2)
    with col_name:
        client_name = st.text_input(
            "委托人姓名 / 公司全称",
            placeholder="例如：张三 或 山西xx贸易有限公司",
        )
    with col_id:
        client_id = st.text_input(
            "身份证号 / 统一社会信用代码",
            placeholder="例如：3702xxxxxxxxxx",
        )

    col_phone, col_addr = st.columns(2)
    with col_phone:
        client_phone = st.text_input("联系电话", placeholder="例如：13800000000")
    with col_addr:
        client_address = st.text_input(
            "联系地址（送达地址）", placeholder="例如：山西省太原市…"
        )

    if client_type == "公司/法人":
        col_rep, col_job = st.columns(2)
        with col_rep:
            legal_rep = st.text_input("法定代表人", placeholder="姓名")
        with col_job:
            legal_rep_job = st.text_input("职务", placeholder="例如：执行董事")
    else:
        legal_rep = ""
        legal_rep_job = ""

# ===========================================================================
# II. 对方当事人
# ===========================================================================
with st.container(border=True):
    st.markdown("#### 📋 对方当事人")

    col_opp1, col_opp2 = st.columns(2)
    with col_opp1:
        opponent1 = st.text_input("被告 / 对方当事人 1", placeholder="例如：李四")
    with col_opp2:
        opponent2 = st.text_input(
            "被告 / 对方当事人 2（选填）", placeholder="如果没有，请留空"
        )

# ===========================================================================
# III. 律师团队
# ===========================================================================
with st.container(border=True):
    st.markdown("#### 👔 律师团队")

    col_ml, col_mp = st.columns(2)
    with col_ml:
        main_lawyer = st.text_input(
            "主办律师", value=config.get("main_lawyer", "")
        )
    with col_mp:
        lawyer_phone = st.text_input(
            "律师电话", value=config.get("lawyer_phone", "")
        )

    sec_lawyer = st.text_input("辅办律师 / 助理", placeholder="例如：某某")

# ===========================================================================
# IV. 案件核心
# ===========================================================================
with st.container(border=True):
    st.markdown("#### 📝 案件核心信息")

    case_reason = st.text_input("案由", placeholder="例如：民间借贷纠纷")

    procedure_list = st.multiselect(
        "审理程序 / 委托事项",
        ["一审", "二审", "执行", "再审", "仲裁"],
        default=["一审"],
    )
    procedure_str = "、".join(procedure_list)

    dispute_amount = st.text_input(
        "争议金额 / 标的额", placeholder="例如：500万元"
    )

    sign_date = st.date_input("签署 / 接待时间", datetime.now())
    date_str = sign_date.strftime("%Y年%m月%d日")

# ===========================================================================
# V. 诉讼地位 & 代理权限
# ===========================================================================
with st.container(border=True):
    st.markdown("#### 📜 诉讼地位与代理权限")

    col_role, col_auth = st.columns(2)
    with col_role:
        role_type = st.radio(
            "诉讼地位",
            ["原告/申请人", "被告/被执行人"],
            horizontal=True,
        )
    with col_auth:
        auth_type = st.radio(
            "代理类型",
            ["一般代理", "特别授权"],
            horizontal=True,
        )

    SPECIAL_POWERS = [
        "代为承认",
        "放弃",
        "变更诉讼请求",
        "进行和解",
        "提起反诉",
        "提起上诉",
        "申请执行",
        "代收法律文书",
        "代为应诉",
        "代为提起上诉",
    ]

    if auth_type == "特别授权":
        # Dynamic defaults based on litigant role
        if role_type == "被告/被执行人":
            default_powers = [
                "代为承认", "放弃", "变更诉讼请求",
                "进行和解", "代收法律文书", "代为应诉",
            ]
        else:
            default_powers = [
                "代为承认", "放弃", "变更诉讼请求",
                "进行和解", "代收法律文书", "代为提起上诉",
            ]

        auth_details = st.multiselect(
            "特别授权事项",
            SPECIAL_POWERS,
            default=default_powers,
            help="根据诉讼地位已自动预选，可按需增删",
        )
        auth_str = (
            "特别授权：" + "、".join(auth_details) if auth_details else "特别授权"
        )
    else:
        auth_details = []
        auth_str = "一般代理"

# ===========================================================================
# VI. 代理费条款（Sentence Builder）
# ===========================================================================
with st.container(border=True):
    st.markdown("#### 💰 代理费条款")

    fee_mode = st.radio(
        "收费方式",
        ["固定收费", "风险代理", "固定+风险"],
        horizontal=True,
    )

    if fee_mode == "固定收费":
        fee_fixed_amount = st.text_input(
            "固定代理费金额", placeholder="例如：30000"
        )
        payment_deadline = st.text_input(
            "支付期限",
            value="甲方收到每笔执行回款之日起三日内",
        )
        fee_clause = (
            f"经双方协商同意，本合同为固定收费。"
            f"甲方应向乙方支付律师代理费人民币 {fee_fixed_amount} 元。"
            f"支付期限为：{payment_deadline}。"
        )

    elif fee_mode == "风险代理":
        fee_risk_condition = st.text_input(
            "风险代理条件",
            placeholder="例如：执行回款金额的 10%",
        )
        payment_deadline = st.text_input(
            "支付期限",
            value="甲方收到每笔执行回款之日起三日内",
        )
        fee_clause = (
            f"经双方协商同意，本合同为风险代理。"
            f"按 {fee_risk_condition} 支付律师代理费。"
            f"支付期限为：{payment_deadline}。"
        )

    else:  # 固定+风险
        fee_fixed_amount = st.text_input(
            "固定部分金额", placeholder="例如：10000"
        )
        fee_risk_condition = st.text_input(
            "风险部分条件",
            placeholder="例如：执行回款金额的 10%",
        )
        payment_deadline = st.text_input(
            "支付期限",
            value="甲方收到每笔执行回款之日起三日内",
        )
        fee_clause = (
            f"经双方协商同意，本合同为固定收费加风险代理。"
            f"甲方应向乙方支付固定律师代理费人民币 {fee_fixed_amount} 元，"
            f"另按 {fee_risk_condition} 支付风险代理费。"
            f"支付期限为：{payment_deadline}。"
        )

    with st.expander("预览代理费条款"):
        st.info(fee_clause)

st.divider()

# ===========================================================================
# Generate
# ===========================================================================
if st.button("生成全套法律文书", type="primary", use_container_width=True):
    if not client_name:
        st.error("请至少输入委托人名称。")
    else:
        data = {
            # 委托人
            "委托人": client_name,
            "甲方": client_name,
            "身份证号": client_id,
            "电话": client_phone,
            "地址": client_address,
            "法定代表人": legal_rep,
            "职务": legal_rep_job,
            # 对方
            "对方当事人": opponent1,
            "被告": opponent1,
            "被告2": opponent2,
            # 律师
            "主办律师": main_lawyer,
            "律师电话": lawyer_phone,
            "辅办律师": sec_lawyer,
            "律所名称": config.get("firm_name", ""),
            # 案件
            "案由": case_reason,
            "委托事项范围": procedure_str,
            "争议金额": dispute_amount,
            "代理权限": auth_str,
            "诉讼地位": role_type,
            "代理费条款": fee_clause,
            # 日期
            "日期": date_str,
            "年": str(sign_date.year),
            "月": str(sign_date.month),
            "日": str(sign_date.day),
        }

        output_dir = os.path.join("output", client_name)
        os.makedirs(output_dir, exist_ok=True)

        template_dir = "templates"
        success_count = 0

        if os.path.exists(template_dir):
            for file in os.listdir(template_dir):
                if file.endswith(".docx") and not file.startswith("~$"):
                    try:
                        doc = DocxTemplate(os.path.join(template_dir, file))
                        doc.render(data)
                        base = os.path.splitext(file)[0]
                        out_name = f"{base}（{client_name}）.docx"
                        doc.save(os.path.join(output_dir, out_name))
                        success_count += 1
                    except Exception as e:
                        st.error(f"文件 {file} 生成失败：{e}")

            if success_count > 0:
                st.balloons()
                st.success(
                    f"共生成 {success_count} 份文书，已保存至 `output/{client_name}/`"
                )
                with st.expander("查看已生成文件", expanded=True):
                    for f in sorted(os.listdir(output_dir)):
                        if f.endswith(".docx"):
                            st.markdown(f"- {f}")
            else:
                st.warning("未找到可用的模板文件。")
        else:
            st.error("找不到 `templates/` 文件夹，请检查项目目录结构。")

