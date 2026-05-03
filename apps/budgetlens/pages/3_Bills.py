import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS
from src.bill_calculator import (
    FREQUENCY_CONFIG, FREQUENCY_LABELS,
    monthly_equivalent, next_charge_date, bill_status, hit_months,
)

st.set_page_config(page_title="Bills — BudgetLens", layout="wide")
st.title("🧾 Bills Manager")

# ── Load bills ─────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        bills = pd.read_sql(
            text("SELECT * FROM budgetlens.bills ORDER BY active DESC, name"),
            conn,
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# ── Total committed ────────────────────────────────────────────────────────────

active_bills = bills[bills["active"] == True] if not bills.empty else pd.DataFrame()
total_monthly = float(active_bills["monthly_equivalent"].sum()) if not active_bills.empty else 0.0

st.metric("Total Committed Monthly Spend", f"${total_monthly:,.2f}")
st.caption("Sum of all active bills converted to monthly equivalents")
st.markdown("---")

# ── Bill cards ────────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "paid":     ("🟢", "#16A34A"),
    "due_soon": ("🟡", "#D97706"),
    "overdue":  ("🔴", "#DC2626"),
    "upcoming": ("⚪", "#6B7280"),
}

today = date.today()
from_month = date(today.year, today.month, 1)

if bills.empty:
    st.info("No bills configured yet. Use the form below or mark a transaction as a bill from the Transactions page.")
else:
    for _, b in bills.iterrows():
        last = b["last_charge_date"]
        nxt = b["next_charge_date"]
        if hasattr(last, "date"):
            last = last.date() if pd.notna(last) else None
        else:
            last = last if (last is not None and not pd.isna(last)) else None

        if hasattr(nxt, "date"):
            nxt = nxt.date() if pd.notna(nxt) else None
        else:
            nxt = nxt if (nxt is not None and not pd.isna(nxt)) else None

        status = bill_status(nxt, last, b["frequency"])
        emoji, color = STATUS_COLORS[status]

        active_label = "" if b["active"] else " *(inactive)*"

        with st.expander(
            f"{emoji} **{b['name']}**{active_label}  —  "
            f"${float(b['amount']):,.2f} {FREQUENCY_LABELS[b['frequency']]}  →  "
            f"**${float(b['monthly_equivalent']):,.2f}/month**",
            expanded=False,
        ):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Category:** {CATEGORY_LABELS.get(b['category'], b['category'])}")
            col2.markdown(f"**Last charge:** {last or 'Unknown'}")
            col3.markdown(f"**Next charge:** {nxt or 'Unknown'}")

            # Calendar strip — next 12 months
            st.markdown("**Charge calendar (next 12 months):**")
            start_date = b["start_date"]
            if hasattr(start_date, "date"):
                start_date = start_date.date()

            hit = hit_months(start_date, b["frequency"], from_month, 12)
            month_cells = []
            for i in range(12):
                m = from_month.replace(month=(from_month.month - 1 + i) % 12 + 1,
                                       year=from_month.year + (from_month.month - 1 + i) // 12)
                label = m.strftime("%b")
                mkey = m.strftime("%Y-%m")
                if mkey in hit:
                    month_cells.append(f"**:blue[{label}]**")
                else:
                    month_cells.append(label)
            st.markdown(" · ".join(month_cells))

            if b["notes"]:
                st.caption(f"Notes: {b['notes']}")

            edit_col, del_col = st.columns([1, 1])
            with edit_col:
                if st.button("✏️ Edit", key=f"edit_{b['id']}"):
                    st.session_state["editing_bill"] = str(b["id"])
            with del_col:
                if st.button("🗑️ Delete", key=f"del_{b['id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("DELETE FROM budgetlens.bills WHERE id = :id"),
                                {"id": str(b["id"])},
                            )
                        st.success(f"Deleted bill: {b['name']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

# ── Edit bill modal ────────────────────────────────────────────────────────────

if "editing_bill" in st.session_state and not bills.empty:
    editing_id = st.session_state["editing_bill"]
    row = bills[bills["id"].astype(str) == editing_id]
    if not row.empty:
        b = row.iloc[0]
        st.markdown("---")
        st.subheader(f"Edit: {b['name']}")

        new_name = st.text_input("Name", value=b["name"], key="edit_name")
        new_cat = st.selectbox(
            "Category",
            ALL_CATEGORIES,
            index=ALL_CATEGORIES.index(b["category"]) if b["category"] in ALL_CATEGORIES else 0,
            format_func=lambda c: CATEGORY_LABELS.get(c, c),
            key="edit_cat",
        )
        ec1, ec2 = st.columns(2)
        with ec1:
            new_freq = st.selectbox(
                "Frequency",
                list(FREQUENCY_CONFIG.keys()),
                index=list(FREQUENCY_CONFIG.keys()).index(b["frequency"]),
                format_func=lambda f: FREQUENCY_LABELS[f],
                key="edit_freq",
            )
        with ec2:
            new_amount = st.number_input("Amount ($)", value=float(b["amount"]), min_value=0.01, key="edit_amount")

        me_preview = monthly_equivalent(new_amount, new_freq)
        st.info(f"Monthly equivalent: **${me_preview:,.2f}/month**")

        new_active = st.checkbox("Active", value=bool(b["active"]), key="edit_active")
        new_notes = st.text_area("Notes", value=b["notes"] or "", key="edit_notes")

        sc1, sc2 = st.columns([1, 4])
        with sc1:
            if st.button("Save Changes", type="primary", key="edit_save"):
                try:
                    with get_engine().begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE budgetlens.bills
                                SET name = :name, category = :cat, frequency = :freq,
                                    amount = :amt, monthly_equivalent = :me,
                                    active = :active, notes = :notes
                                WHERE id = :id
                            """),
                            {"name": new_name, "cat": new_cat, "freq": new_freq,
                             "amt": new_amount, "me": me_preview, "active": new_active,
                             "notes": new_notes or None, "id": editing_id},
                        )
                    del st.session_state["editing_bill"]
                    st.success("Bill updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with sc2:
            if st.button("Cancel", key="edit_cancel"):
                del st.session_state["editing_bill"]
                st.rerun()

# ── Add new bill ───────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Add New Bill")

a1, a2 = st.columns(2)
with a1:
    name = st.text_input("Bill name *", placeholder="e.g. Netflix", key="add_name")
    amount = st.number_input("Amount ($) *", min_value=0.01, step=0.01, key="add_amount")
    start = st.date_input("First charge date *", value=today, key="add_start")
with a2:
    category = st.selectbox(
        "Category",
        ALL_CATEGORIES,
        format_func=lambda c: CATEGORY_LABELS.get(c, c),
        key="add_category",
    )
    frequency = st.selectbox(
        "Frequency",
        list(FREQUENCY_CONFIG.keys()),
        format_func=lambda f: FREQUENCY_LABELS[f],
        key="add_frequency",
    )
    notes = st.text_input("Notes (optional)", key="add_notes")

me = monthly_equivalent(amount, frequency)
st.info(f"Monthly equivalent: **${me:,.2f}/month**")

if st.button("➕ Add Bill", type="primary", key="add_submit"):
    if not name:
        st.error("Bill name is required.")
    else:
        ncd = next_charge_date(start, frequency)
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO budgetlens.bills
                            (name, category, frequency, amount, monthly_equivalent,
                             start_date, last_charge_date, next_charge_date, notes)
                        VALUES
                            (:name, :cat, :freq, :amt, :me, :sd, :lcd, :ncd, :notes)
                    """),
                    {"name": name, "cat": category, "freq": frequency,
                     "amt": amount, "me": me, "sd": start, "lcd": start,
                     "ncd": ncd, "notes": notes or None},
                )
            st.success(f"Bill **{name}** added — ${me:,.2f}/month")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add bill: {e}")
