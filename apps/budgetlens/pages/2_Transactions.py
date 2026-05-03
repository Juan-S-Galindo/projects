import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
        cat_filter = next((c for c in ALL_CATEGORIES if CATEGORY_LABELS.get(c, c) == selected_cat_label), None)

with col4:
    search = st.text_input("Search description", placeholder="e.g. Amazon")

# ── Load ───────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        where = ["1=1"]
        params: dict = {}
        if selected_month != "all":
            where.append("to_char(transaction_date, 'YYYY-MM') = :m")
            params["m"] = selected_month
        if source_filter == "Chase":
            where.append("source = 'chase'")
        elif source_filter == "Bank of America":
            where.append("source = 'boa'")
        if cat_filter:
            where.append("category = :cat")
            params["cat"] = cat_filter
        if search:
            where.append("LOWER(description) LIKE :search")
            params["search"] = f"%{search.lower()}%"

        query = f"""
            SELECT id, source, transaction_date, description, category,
                   category_overridden, transaction_type, amount, bill_id
            FROM budgetlens.transactions
            WHERE {' AND '.join(where)}
            ORDER BY transaction_date DESC
            LIMIT 500
        """
        df = pd.read_sql(text(query), conn, params=params)
except Exception as e:
    st.error(f"Failed to load transactions: {e}")
    st.stop()

if df.empty:
    st.info("No transactions found for the selected filters.")
    st.stop()

st.caption(f"Showing {len(df)} transaction(s)")

# ── Display / edit ─────────────────────────────────────────────────────────────

cat_label_map = {CATEGORY_LABELS.get(c, c): c for c in ALL_CATEGORIES}
label_options = list(cat_label_map.keys())

display = df.copy()
display["Category"] = display["category"].map(lambda c: CATEGORY_LABELS.get(c, c))
display["Source"] = display["source"].map({"chase": "Chase", "boa": "BOA"})
display["Date"] = display["transaction_date"].astype(str)
display["Amount ($)"] = display["amount"].astype(float)
display["Is Bill"] = display["bill_id"].notna()

edited = st.data_editor(
    display[["Date", "Source", "description", "Amount ($)", "Category", "Is Bill"]].rename(
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
        "Is Bill": st.column_config.CheckboxColumn(disabled=True, width="small"),
    },
    hide_index=True,
    use_container_width=True,
)

# ── Save category overrides ────────────────────────────────────────────────────

if st.button("💾 Save Category Changes", type="primary"):
    new_cats = edited["Category"].map(cat_label_map)
    changed = new_cats.values != display["Category"].map(cat_label_map).values
    ids = df["id"].values

    if not changed.any():
        st.info("No changes to save.")
    else:
        try:
            with get_engine().begin() as conn:
                for i, (row_changed, new_cat, tid) in enumerate(
                    zip(changed, new_cats, ids)
                ):
                    if row_changed:
                        conn.execute(
                            text("""
                                UPDATE budgetlens.transactions
                                SET category = :cat, category_overridden = TRUE
                                WHERE id = :id
                            """),
                            {"cat": new_cat, "id": str(tid)},
                        )
            n = int(changed.sum())
            st.success(f"Updated {n} transaction(s).")
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")

# ── Mark as Bill shortcut ──────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Mark a Transaction as a Bill")

selected_idx = st.selectbox(
    "Select transaction",
    options=range(len(df)),
    format_func=lambda i: f"{df.iloc[i]['transaction_date']} — {df.iloc[i]['description']} (${abs(float(df.iloc[i]['amount'])):,.2f})",
)

if df.iloc[selected_idx]["bill_id"] is not None:
    st.info("This transaction is already linked to a bill.")
else:
    with st.form("promote_to_bill"):
        st.write(f"**{df.iloc[selected_idx]['description']}**")
        bill_name = st.text_input("Bill name", value=df.iloc[selected_idx]["description"][:40])
        bill_freq = st.selectbox(
            "Frequency",
            ["monthly", "weekly", "every_2_months", "quarterly", "every_6_months", "yearly"],
            format_func=lambda f: {
                "weekly": "Weekly",
                "monthly": "Monthly",
                "every_2_months": "Every 2 months",
                "quarterly": "Quarterly",
                "every_6_months": "Every 6 months",
                "yearly": "Yearly",
            }[f],
        )
        bill_cat = st.selectbox(
            "Category",
            ALL_CATEGORIES,
            format_func=lambda c: CATEGORY_LABELS.get(c, c),
            index=ALL_CATEGORIES.index(df.iloc[selected_idx]["category"])
            if df.iloc[selected_idx]["category"] in ALL_CATEGORIES else 0,
        )
        submitted = st.form_submit_button("Create Bill")

    if submitted:
        from src.bill_calculator import monthly_equivalent, next_charge_date
        amt = abs(float(df.iloc[selected_idx]["amount"]))
        me = monthly_equivalent(amt, bill_freq)
        t_date = df.iloc[selected_idx]["transaction_date"]
        if hasattr(t_date, "date"):
            t_date = t_date.date()
        ncd = next_charge_date(t_date, bill_freq)
        tid = str(df.iloc[selected_idx]["id"])

        try:
            with get_engine().begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO budgetlens.bills
                            (name, category, frequency, amount, monthly_equivalent,
                             start_date, last_charge_date, next_charge_date)
                        VALUES (:name, :cat, :freq, :amt, :me, :sd, :lcd, :ncd)
                        RETURNING id
                    """),
                    {"name": bill_name, "cat": bill_cat, "freq": bill_freq,
                     "amt": amt, "me": me, "sd": t_date, "lcd": t_date, "ncd": ncd},
                )
                bill_id = str(result.fetchone()[0])
                conn.execute(
                    text("UPDATE budgetlens.transactions SET bill_id = :bid WHERE id = :tid"),
                    {"bid": bill_id, "tid": tid},
                )
                conn.execute(
                    text("INSERT INTO budgetlens.bill_transactions (bill_id, transaction_id) VALUES (:bid, :tid)"),
                    {"bid": bill_id, "tid": tid},
                )
            st.success(f"Bill **{bill_name}** created! Monthly equivalent: ${me:,.2f}/month")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to create bill: {e}")
