import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re as _re
import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS

st.set_page_config(page_title="Transactions — BudgetLens", layout="wide")
st.title("📋 Transactions")

# ── Filters ────────────────────────────────────────────────────────────────────

today = date.today()
col1, col2, col3, col4 = st.columns([2, 2, 2, 3])

with col1:
    months = [
        date(today.year if today.month - i > 0 else today.year - 1,
             (today.month - i - 1) % 12 + 1, 1)
        for i in range(24)
    ]
    month_opts = {m.strftime("%B %Y"): m.strftime("%Y-%m") for m in months}
    month_opts["All time"] = "all"
    selected_month_label = st.selectbox("Month", list(month_opts.keys()))
    selected_month = month_opts[selected_month_label]

with col2:
    source_filter = st.selectbox("Source", ["All", "Chase", "Bank of America"])

with col3:
    cat_labels = ["All"] + [CATEGORY_LABELS.get(c, c) for c in ALL_CATEGORIES]
    selected_cat_label = st.selectbox("Category", cat_labels)
    cat_filter = None
    if selected_cat_label != "All":
        cat_filter = next(
            (c for c in ALL_CATEGORIES if CATEGORY_LABELS.get(c, c) == selected_cat_label), None
        )

with col4:
    search = st.text_input("Search description", placeholder="e.g. Amazon")

# ── Load ───────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        where = ["1=1"]
        params: dict = {}
        if selected_month != "all":
            where.append("to_char(td.transaction_date, 'YYYY-MM') = :m")
            params["m"] = selected_month
        if source_filter == "Chase":
            where.append("td.source = 'chase'")
        elif source_filter == "Bank of America":
            where.append("td.source = 'boa'")
        if cat_filter:
            where.append("td.category = :cat")
            params["cat"] = cat_filter
        else:
            where.append("td.category NOT IN ('transfer', 'credit_card_payment')")
        if search:
            where.append("LOWER(td.description) LIKE :search")
            params["search"] = f"%{search.lower()}%"

        query = f"""
            SELECT
                td.id,
                td.source,
                td.transaction_date,
                td.description,
                td.category,
                td.category_overridden,
                td.transaction_type,
                td.amount,
                td.content_hash,
                td.txn_hash,
                td.bill_id IS NOT NULL AS is_bill
            FROM budgetlens.transactions_deduped td
            WHERE {' AND '.join(where)}
            ORDER BY td.transaction_date DESC
            LIMIT 500
        """
        df = pd.read_sql(text(query), conn, params=params)

        income_sources = pd.read_sql(
            text("""
                SELECT filter_type, filter_value
                FROM budgetlens.income_transaction_sources
                WHERE active = TRUE AND filter_value IS NOT NULL
            """),
            conn,
        )
except Exception as e:
    st.error(f"Failed to load transactions: {e}")
    st.stop()

if df.empty:
    st.info("No transactions found for the selected filters.")
    st.stop()

st.caption(f"Showing {len(df)} transaction(s)")

# ── Editable table ─────────────────────────────────────────────────────────────

cat_label_map = {CATEGORY_LABELS.get(c, c): c for c in ALL_CATEGORIES}
label_options = list(cat_label_map.keys())

def _matches_any_source(desc: str, sources: pd.DataFrame) -> bool:
    lower = desc.lower()
    for _, src in sources.iterrows():
        fv = src["filter_value"]
        ft = src["filter_type"]
        try:
            if ft == "contains" and fv.lower() in lower:
                return True
            elif ft == "starts_with" and lower.startswith(fv.lower()):
                return True
            elif ft == "regex" and _re.search(fv, desc, _re.IGNORECASE):
                return True
        except Exception:
            pass
    return False

display = df.copy()
display["Category"] = display["category"].map(lambda c: CATEGORY_LABELS.get(c, c))
display["Source"] = display["source"].map({"chase": "Chase", "boa": "BOA"})
display["Date"] = display["transaction_date"].astype(str)
display["Amount ($)"] = display["amount"].astype(float)
display["Bill"] = display["is_bill"].astype(bool)
if not income_sources.empty:
    display["Income"] = display["description"].apply(
        lambda d: _matches_any_source(d, income_sources)
    )
else:
    display["Income"] = False

edited = st.data_editor(
    display[["Date", "Source", "description", "Amount ($)", "Category", "Bill", "Income"]].rename(
        columns={"description": "Description"}
    ),
    column_config={
        "Date": st.column_config.TextColumn(disabled=True, width="small"),
        "Source": st.column_config.TextColumn(disabled=True, width="small"),
        "Description": st.column_config.TextColumn(disabled=True, width="large"),
        "Amount ($)": st.column_config.NumberColumn(disabled=True, format="$%.2f", width="small"),
        "Category": st.column_config.SelectboxColumn(
            "Category", options=label_options, width="medium"
        ),
        "Bill": st.column_config.CheckboxColumn("Bill", disabled=True, width="small"),
        "Income": st.column_config.CheckboxColumn("Income", disabled=True, width="small"),
    },
    hide_index=True,
    use_container_width=True,
)

# ── Save — category overrides ──────────────────────────────────────────────────

if st.button("💾 Save Changes", type="primary"):
    new_cats = edited["Category"].map(cat_label_map)
    cat_changed = new_cats.values != display["Category"].map(cat_label_map).values

    try:
        with get_engine().begin() as conn:
            for i, (changed, new_cat) in enumerate(zip(cat_changed, new_cats)):
                if changed:
                    conn.execute(
                        text("""
                            INSERT INTO budgetlens.transaction_attributes
                                (txn_hash, category, category_overridden)
                            VALUES (:txn_hash, :cat, TRUE)
                            ON CONFLICT (txn_hash) DO UPDATE
                                SET category = EXCLUDED.category,
                                    category_overridden = TRUE,
                                    updated_at = NOW()
                        """),
                        {"txn_hash": df.iloc[i]["txn_hash"], "cat": new_cat},
                    )

        if cat_changed.any():
            st.success(f"{int(cat_changed.sum())} category change(s) saved")
        st.rerun()

    except Exception as e:
        st.error(f"Save failed: {e}")
