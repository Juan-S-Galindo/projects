import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from src.ingestor.pipeline import parse_file, ingest, count_already_in_staging
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS

st.set_page_config(page_title="Import — BudgetLens", layout="wide")
st.title("📥 Import Bank CSV")

st.markdown(
    "Upload a **Chase** or **Bank of America** CSV export. "
    "The format is detected automatically. "
    "Re-uploading the same file is safe — the deduplication view always shows "
    "the latest version of each transaction."
)

# Accept both .csv and .CSV (Streamlit's type filter is case-sensitive on some
# platforms, so we accept all files and validate the extension ourselves).
uploaded = st.file_uploader(
    "Drop your CSV file here or click to browse",
    type=None,
    key="csv_uploader",
)

if uploaded is None:
    st.info("Supported formats: Chase credit card export · Bank of America checking export")
    st.stop()

if not uploaded.name.lower().endswith(".csv"):
    st.error(f"Expected a .csv file, got: `{uploaded.name}`")
    st.stop()

# ── Parse ──────────────────────────────────────────────────────────────────────

file_bytes = uploaded.read()

try:
    source, df = parse_file(file_bytes)
except ValueError as e:
    st.error(str(e))
    st.stop()

badge_color = "#1D4ED8" if source == "chase" else "#DC2626"
badge_label = "Chase" if source == "chase" else "Bank of America"
st.markdown(
    f'<span style="background:{badge_color};color:#fff;padding:4px 12px;'
    f'border-radius:12px;font-size:0.85rem;font-weight:600">'
    f"✓ {badge_label} detected</span>",
    unsafe_allow_html=True,
)
st.markdown("")

st.markdown(f"**{len(df)} transactions parsed** from `{uploaded.name}`")

# ── Category override in preview ──────────────────────────────────────────────

st.subheader("Preview & Category Override")
st.caption("You can correct any auto-assigned categories before importing.")

display = df[["transaction_date", "description", "amount", "category"]].copy()
display["transaction_date"] = display["transaction_date"].astype(str)
display["category_label"] = display["category"].map(lambda c: CATEGORY_LABELS.get(c, c))

category_options = {CATEGORY_LABELS.get(c, c): c for c in ALL_CATEGORIES}
label_options = list(category_options.keys())

edited = st.data_editor(
    display.rename(columns={
        "transaction_date": "Date",
        "description": "Description",
        "amount": "Amount ($)",
        "category": "category_id",
        "category_label": "Category",
    }),
    column_config={
        "Date": st.column_config.TextColumn(disabled=True, width="small"),
        "Description": st.column_config.TextColumn(disabled=True, width="large"),
        "Amount ($)": st.column_config.NumberColumn(disabled=True, format="$%.2f", width="small"),
        "category_id": None,
        "Category": st.column_config.SelectboxColumn(
            "Category",
            options=label_options,
            width="medium",
        ),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

if edited is not None:
    new_cats = edited["Category"].map(category_options)
    df["category_overridden"] = new_cats.values != df["category"].values
    df["category"] = new_cats.values

# ── Staging info (informational only — not blocking) ──────────────────────────

try:
    already = count_already_in_staging(df)
    genuinely_new = len(df) - already
    if already > 0:
        st.info(
            f"ℹ️ {already} of these transactions are already in staging "
            f"(a new version will be added). "
            f"{genuinely_new} are brand-new."
        )
    else:
        st.info(f"**{len(df)} new transactions** ready to import.")
except Exception:
    pass  # DB might not be set up yet; non-blocking

# ── Confirm import ─────────────────────────────────────────────────────────────

if st.button("✅ Confirm Import", type="primary"):
    with st.spinner("Importing…"):
        try:
            stats = ingest(df)
            st.success(
                f"Imported **{stats['imported']}** transactions into staging. "
                f"The deduplicated view has been updated automatically."
            )
        except Exception as e:
            st.error(f"Import failed: {e}")
