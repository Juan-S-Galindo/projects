import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS
from src.bill_calculator import FREQUENCY_LABELS, FREQUENCY_CONFIG, monthly_equivalent, next_charge_date

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
# is_bill is resolved via bill_transactions JOIN through content_hash so that
# re-importing a file doesn't reset the bill status on already-linked rows.

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
                EXISTS (
                    SELECT 1
                    FROM budgetlens.bill_transactions bt
                    JOIN budgetlens.transactions t ON t.id = bt.transaction_id
                    WHERE t.content_hash = td.content_hash
                ) AS is_bill,
                (
                    SELECT bt.bill_id::text
                    FROM budgetlens.bill_transactions bt
                    JOIN budgetlens.transactions t ON t.id = bt.transaction_id
                    WHERE t.content_hash = td.content_hash
                    LIMIT 1
                ) AS bill_id
            FROM budgetlens.transactions_deduped td
            WHERE {' AND '.join(where)}
            ORDER BY td.transaction_date DESC
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

# ── Editable table ─────────────────────────────────────────────────────────────

cat_label_map = {CATEGORY_LABELS.get(c, c): c for c in ALL_CATEGORIES}
label_options = list(cat_label_map.keys())

display = df.copy()
display["Category"] = display["category"].map(lambda c: CATEGORY_LABELS.get(c, c))
display["Source"] = display["source"].map({"chase": "Chase", "boa": "BOA"})
display["Date"] = display["transaction_date"].astype(str)
display["Amount ($)"] = display["amount"].astype(float)
display["Is Bill"] = display["is_bill"].astype(bool)

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
        "Is Bill": st.column_config.CheckboxColumn(
            "Is Bill", help="Check to mark as a recurring bill", width="small"
        ),
    },
    hide_index=True,
    use_container_width=True,
)

# ── Save — categories + bill toggles ─────────────────────────────────────────

if st.button("💾 Save Changes", type="primary"):
    new_cats = edited["Category"].map(cat_label_map)
    cat_changed = new_cats.values != display["Category"].map(cat_label_map).values

    new_is_bill = edited["Is Bill"].astype(bool).values
    old_is_bill = display["Is Bill"].values
    newly_billed = [i for i, (n, o) in enumerate(zip(new_is_bill, old_is_bill)) if n and not o]
    newly_unbilled = [i for i, (n, o) in enumerate(zip(new_is_bill, old_is_bill)) if not n and o]

    try:
        with get_engine().begin() as conn:
            # Category overrides
            for i, (changed, new_cat) in enumerate(zip(cat_changed, new_cats)):
                if changed:
                    conn.execute(
                        text("""
                            UPDATE budgetlens.transactions
                            SET category = :cat, category_overridden = TRUE
                            WHERE id = :id
                        """),
                        {"cat": new_cat, "id": str(df.iloc[i]["id"])},
                    )

            # Unlink bills (uncheck)
            for i in newly_unbilled:
                content_hash = df.iloc[i]["content_hash"]
                conn.execute(
                    text("""
                        DELETE FROM budgetlens.bill_transactions
                        WHERE transaction_id IN (
                            SELECT id FROM budgetlens.transactions
                            WHERE content_hash = :hash
                        )
                    """),
                    {"hash": content_hash},
                )
                conn.execute(
                    text("""
                        UPDATE budgetlens.transactions
                        SET bill_id = NULL
                        WHERE content_hash = :hash
                    """),
                    {"hash": content_hash},
                )

        msgs = []
        if cat_changed.any():
            msgs.append(f"{int(cat_changed.sum())} category change(s) saved")
        if newly_unbilled:
            msgs.append(f"{len(newly_unbilled)} bill(s) unlinked")
        if msgs:
            st.success(" · ".join(msgs))

        # Store newly-billed row indices for the config form below
        if newly_billed:
            st.session_state["pending_bill_rows"] = newly_billed
            st.session_state["pending_bill_df_snapshot"] = df.copy()
        else:
            st.rerun()

    except Exception as e:
        st.error(f"Save failed: {e}")

# ── Bill configuration form for newly-checked rows ────────────────────────────

pending = st.session_state.get("pending_bill_rows", [])
pending_df = st.session_state.get("pending_bill_df_snapshot", df)

if pending:
    st.markdown("---")
    st.subheader("Configure New Bills")
    st.caption("Set the frequency for each transaction you just marked as a bill.")

    for i in pending:
        row = pending_df.iloc[i]
        amt = abs(float(row["amount"]))
        desc = row["description"]
        t_date = row["transaction_date"]
        if hasattr(t_date, "date"):
            t_date = t_date.date()

        with st.expander(f"🧾 {desc}  —  ${amt:,.2f}", expanded=True):
            with st.form(f"bill_form_{i}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    bill_name = st.text_input("Bill name", value=desc[:50], key=f"bname_{i}")
                with c2:
                    freq = st.selectbox(
                        "Frequency",
                        list(FREQUENCY_CONFIG.keys()),
                        format_func=lambda f: FREQUENCY_LABELS[f],
                        key=f"bfreq_{i}",
                    )
                with c3:
                    bill_cat = st.selectbox(
                        "Category",
                        ALL_CATEGORIES,
                        format_func=lambda c: CATEGORY_LABELS.get(c, c),
                        index=ALL_CATEGORIES.index(row["category"])
                        if row["category"] in ALL_CATEGORIES else 0,
                        key=f"bcat_{i}",
                    )

                me = monthly_equivalent(amt, freq)
                st.info(f"Monthly equivalent: **${me:,.2f}/month**")
                submitted = st.form_submit_button("✅ Create Bill", type="primary")

            if submitted:
                ncd = next_charge_date(t_date, freq)
                content_hash = row["content_hash"]
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
                            {"name": bill_name, "cat": bill_cat, "freq": freq,
                             "amt": amt, "me": me, "sd": t_date, "lcd": t_date, "ncd": ncd},
                        )
                        bill_id = str(result.fetchone()[0])

                        # Link ALL staging rows with this content_hash
                        conn.execute(
                            text("""
                                UPDATE budgetlens.transactions
                                SET bill_id = :bid
                                WHERE content_hash = :hash
                            """),
                            {"bid": bill_id, "hash": content_hash},
                        )
                        conn.execute(
                            text("""
                                INSERT INTO budgetlens.bill_transactions (bill_id, transaction_id)
                                SELECT :bid, id
                                FROM budgetlens.transactions
                                WHERE content_hash = :hash
                                ON CONFLICT DO NOTHING
                            """),
                            {"bid": bill_id, "hash": content_hash},
                        )

                    st.success(f"Bill **{bill_name}** created — ${me:,.2f}/month")
                    remaining = [x for x in st.session_state["pending_bill_rows"] if x != i]
                    st.session_state["pending_bill_rows"] = remaining
                    if not remaining:
                        del st.session_state["pending_bill_rows"]
                        del st.session_state["pending_bill_df_snapshot"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create bill: {e}")
