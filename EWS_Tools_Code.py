import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)

# ==================================================
# COMMON NORMALIZATION
# ==================================================
def normalize_columns(df):
    df = df.copy()
    df.columns = (
        df.columns
        .str.replace("ï»¿", "", regex=False)
        .str.strip()
        .str.lower()
    )
    return df


# ==================================================
# RULE 1 – UNIQUE CENTER PER BM PER DAY
# ==================================================
def apply_rule1(df):
    df = normalize_columns(df)

    required = [
        "state", "branch_name", "region_name",
        "attended by id", "month, day, year of meeting date", "center_id"
    ]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df["month, day, year of meeting date"] = pd.to_datetime(
        df["month, day, year of meeting date"], errors="coerce"
    )

    df = df.drop_duplicates(
        subset=[
            "state", "branch_name", "region_name",
            "attended by id",
            "month, day, year of meeting date",
            "center_id"
        ]
    )

    pivot = pd.pivot_table(
        df,
        index=["state", "branch_name", "region_name", "attended by id"],
        columns="month, day, year of meeting date",
        values="center_id",
        aggfunc=pd.Series.nunique,
        fill_value=0
    ).reset_index()

    id_cols = ["state", "branch_name", "region_name", "attended by id"]
    date_cols = pivot.columns.difference(id_cols)

    pivot["Total"] = pivot[date_cols].sum(axis=1)
    pivot["Days_Visited"] = (pivot[date_cols] > 0).sum(axis=1)

    p97 = pivot["Days_Visited"].quantile(0.975)
    pivot["P97_5"] = p97
    pivot["Above_97_5"] = pivot["Days_Visited"] >= p97

    return pivot


# ==================================================
# RULE 2 – EXACT USER LOGIC
# ==================================================
def apply_rule2(df):
    df = normalize_columns(df)

    required = ["state", "branch_name", "cust_id", "loan_id", "lms_application_status"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df["lms_application_status"] = (
        df["lms_application_status"]
        .str.strip()
        .str.title()
    )

    df = df.drop_duplicates(
        subset=["state", "branch_name", "cust_id", "loan_id", "lms_application_status"]
    )

    pivot = pd.pivot_table(
        df,
        index=["state", "branch_name", "cust_id"],
        columns="lms_application_status",
        values="loan_id",
        aggfunc=pd.Series.nunique,
        fill_value=0
    ).reset_index()

    final_columns = [
        "state", "branch_name", "cust_id",
        "Active", "Bureau Check", "Cgt-1", "Draft",
        "Grt-1", "Pre Sanction", "Pre Sanction Verification",
        "Rejected", "Sanctioned"
    ]

    for col in final_columns:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot = pivot[final_columns]

    status_cols = final_columns[3:]
    pivot["Grand Total"] = pivot[status_cols].sum(axis=1)

    pivot = pivot[pivot["Active"] > 0]
    pivot = pivot.sort_values("Rejected", ascending=False)

    pivot[status_cols + ["Grand Total"]] = (
        pivot[status_cols + ["Grand Total"]].replace(0, "")
    )

    return pivot


# ==================================================
# STREAMLIT UI
# ==================================================
st.set_page_config(
    page_title="Fraud EWS – Automated Rule Tool",
    layout="wide"
)

st.markdown(
    "<h2 style='text-align:center;color:#1F4E79;'>Fraud EWS – Automated Rule Tool</h2>",
    unsafe_allow_html=True
)

uploaded_file = st.file_uploader(
    "📂 Upload CSV File",
    type=["csv"]
)

if uploaded_file:
    df = pd.read_csv(uploaded_file, encoding="latin1")
    st.success("File uploaded successfully ✅")

    st.subheader("🔍 Data Preview (Top 5 Rows)")
    st.dataframe(df.head(), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Run Rule 1"):
            try:
                res1 = apply_rule1(df)
                st.success("Rule 1 completed ✅")
                st.dataframe(res1, use_container_width=True)

                st.download_button(
                    "⬇️ Download Rule 1 Output",
                    data=res1.to_excel(index=False),
                    file_name="Rule_1_Output.xlsx"
                )
            except Exception as e:
                st.error(str(e))

    with col2:
        if st.button("⚡ Run Rule 2"):
            try:
                res2 = apply_rule2(df)
                st.success("Rule 2 completed ✅")
                st.dataframe(res2, use_container_width=True)

                st.download_button(
                    "⬇️ Download Rule 2 Output",
                    data=res2.to_excel(index=False),
                    file_name="Rule_2_Output.xlsx"
                )
            except Exception as e:
                st.error(str(e))

else:
    st.info("Please upload a CSV file to begin.")

st.markdown(
    "<hr><p style='text-align:center;font-size:13px;'>Developed by <b>Faiz Khan</b> | Risk</p>",
    unsafe_allow_html=True
)
