import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.db.connection import get_engine

st.set_page_config(page_title="Income — BudgetLens", layout="wide")
st.title("💰 Income")

CADENCE_OPTIONS = {
    "monthly":      {"label": "Monthly",      "per_year": 12},
    "semi_monthly": {"label": "Semi-Monthly",  "per_year": 24},
    "biweekly":     {"label": "Biweekly",      "per_year": 26},
}


def monthly_from_cadence(amount: float, cadence: str) -> float:
    return amount * CADENCE_OPTIONS[cadence]["per_year"] / 12


# ── Load ──────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        cadence_row = conn.execute(
            text("SELECT value FROM budgetlens.settings WHERE key = 'pay_cadence'")
        ).fetchone()
        cadence = cadence_row[0] if cadence_row else "semi_monthly"

        income_txns = pd.read_sql(
            text("""
                SELECT
                    description,
                    COUNT(*)                    AS occurrences,
                    AVG(amount)                 AS avg_amount,
                    MAX(transaction_date)       AS last_seen
                FROM budgetlens.transactions_deduped
                WHERE category = 'income'
                GROUP BY description
                ORDER BY avg_amount DESC
            """),
            conn,
        )

        rules_df = pd.read_sql(
            text("SELECT description, is_regular FROM budgetlens.income_transaction_rules"),
            conn,
        )

        sources_df = pd.read_sql(
            text("SELECT * FROM budgetlens.income_sources ORDER BY name"),
            conn,
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

rules = dict(zip(rules_df["description"], rules_df["is_regular"])) if not rules_df.empty else {}

# ── Pay Cadence ───────────────────────────────────────────────────────────────

st.subheader("Pay Cadence")
st.caption("How often do you receive your primary paycheck?")

new_cadence = st.selectbox(
    "Cadence",
    list(CADENCE_OPTIONS.keys()),
    index=list(CADENCE_OPTIONS.keys()).index(cadence),
    format_func=lambda c: CADENCE_OPTIONS[c]["label"],
    key="cadence_select",
)
if new_cadence != cadence:
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE budgetlens.settings SET value = :v WHERE key = 'pay_cadence'"),
                {"v": new_cadence},
            )
        cadence = new_cadence
        st.success("Pay cadence updated.")
    except Exception as e:
        st.error(f"Failed to save cadence: {e}")

st.markdown("---")

# ── Income from Transactions ──────────────────────────────────────────────────

st.subheader("Income from Transactions")
st.caption(
    "Select which transaction descriptions count as regular income. "
    "Deselect one-time payments like bonuses or reimbursements."
)

if income_txns.empty:
    st.info("No income transactions found. Import transactions categorized as income to get started.")
else:
    updated_rules: dict[str, bool] = {}
    any_changed = False

    for _, row in income_txns.iterrows():
        desc = row["description"]
        avg = abs(float(row["avg_amount"]))
        count = int(row["occurrences"])
        last = str(row["last_seen"])[:10]
        monthly = monthly_from_cadence(avg, cadence)

        is_regular = rules.get(desc, True)

        col_chk, col_desc, col_avg, col_mo, col_cnt, col_last = st.columns([1, 5, 2, 2, 1, 2])
        with col_chk:
            new_val = st.checkbox("", value=is_regular, key=f"inc_{desc}", label_visibility="collapsed")
        with col_desc:
            st.markdown(f"{'**' if new_val else '~~'}{desc}{'**' if new_val else '~~'}")
        with col_avg:
            st.caption(f"avg ${avg:,.2f}/check")
        with col_mo:
            st.caption(f"**${monthly:,.2f}/mo**" if new_val else f"~~${monthly:,.2f}/mo~~")
        with col_cnt:
            st.caption(f"{count}×")
        with col_last:
            st.caption(last)

        updated_rules[desc] = new_val
        if new_val != is_regular:
            any_changed = True

    if st.button("💾 Save Income Selections", type="primary", disabled=not any_changed):
        try:
            with get_engine().begin() as conn:
                for desc, is_reg in updated_rules.items():
                    conn.execute(
                        text("""
                            INSERT INTO budgetlens.income_transaction_rules (description, is_regular)
                            VALUES (:desc, :reg)
                            ON CONFLICT (description) DO UPDATE SET is_regular = EXCLUDED.is_regular
                        """),
                        {"desc": desc, "reg": is_reg},
                    )
            st.success("Income selections saved.")
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")

st.markdown("---")

# ── Custom Income Sources ─────────────────────────────────────────────────────

st.subheader("Custom Income Sources")
st.caption("Add income not captured by your bank transactions (freelance, side income, etc.).")

if not sources_df.empty:
    for _, src in sources_df.iterrows():
        monthly = monthly_from_cadence(float(src["amount"]), src["cadence"])
        cadence_label = CADENCE_OPTIONS.get(src["cadence"], {}).get("label", src["cadence"])
        active_label = "" if src["active"] else " *(inactive)*"

        with st.expander(
            f"**{src['name']}**{active_label}  —  "
            f"${float(src['amount']):,.2f} {cadence_label}  →  **${monthly:,.2f}/mo**",
            expanded=False,
        ):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                new_name = st.text_input("Name", value=src["name"], key=f"sname_{src['id']}")
            with ec2:
                new_amount = st.number_input("Amount ($)", value=float(src["amount"]), min_value=0.01, key=f"samt_{src['id']}")
            with ec3:
                new_cad = st.selectbox(
                    "Cadence",
                    list(CADENCE_OPTIONS.keys()),
                    index=list(CADENCE_OPTIONS.keys()).index(src["cadence"])
                    if src["cadence"] in CADENCE_OPTIONS else 0,
                    format_func=lambda c: CADENCE_OPTIONS[c]["label"],
                    key=f"scad_{src['id']}",
                )

            new_monthly = monthly_from_cadence(new_amount, new_cad)
            st.info(f"Monthly equivalent: **${new_monthly:,.2f}/month**")

            new_active = st.checkbox("Active", value=bool(src["active"]), key=f"sact_{src['id']}")

            sc1, sc2 = st.columns([1, 1])
            with sc1:
                if st.button("Save", key=f"ssave_{src['id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("""
                                    UPDATE budgetlens.income_sources
                                    SET name = :name, amount = :amt, cadence = :cad, active = :active
                                    WHERE id = :id
                                """),
                                {"name": new_name, "amt": new_amount, "cad": new_cad,
                                 "active": new_active, "id": str(src["id"])},
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")
            with sc2:
                if st.button("🗑️ Delete", key=f"sdel_{src['id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("DELETE FROM budgetlens.income_sources WHERE id = :id"),
                                {"id": str(src["id"])},
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

st.markdown("---")
st.subheader("Add Custom Income Source")

a1, a2, a3 = st.columns(3)
with a1:
    add_name = st.text_input("Name *", placeholder="e.g. Freelance", key="add_src_name")
with a2:
    add_amount = st.number_input("Amount per paycheck ($) *", min_value=0.01, step=100.0, key="add_src_amount")
with a3:
    add_cadence = st.selectbox(
        "Cadence",
        list(CADENCE_OPTIONS.keys()),
        index=1,
        format_func=lambda c: CADENCE_OPTIONS[c]["label"],
        key="add_src_cadence",
    )

add_monthly = monthly_from_cadence(add_amount, add_cadence)
st.info(f"Monthly equivalent: **${add_monthly:,.2f}/month**")

if st.button("➕ Add Income Source", type="primary", key="add_src_submit"):
    if not add_name:
        st.error("Name is required.")
    else:
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO budgetlens.income_sources (name, amount, cadence)
                        VALUES (:name, :amt, :cad)
                    """),
                    {"name": add_name, "amt": add_amount, "cad": add_cadence},
                )
            st.success(f"Added **{add_name}** — ${add_monthly:,.2f}/month")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add income source: {e}")

st.markdown("---")

# ── Monthly Income Summary ────────────────────────────────────────────────────

st.subheader("Monthly Income Summary")

txn_monthly = 0.0
if not income_txns.empty:
    for _, row in income_txns.iterrows():
        desc = row["description"]
        is_regular = rules.get(desc, True)
        if is_regular:
            txn_monthly += monthly_from_cadence(abs(float(row["avg_amount"])), cadence)

custom_monthly = 0.0
if not sources_df.empty:
    active_sources = sources_df[sources_df["active"] == True]
    for _, src in active_sources.iterrows():
        custom_monthly += monthly_from_cadence(float(src["amount"]), src["cadence"])

total_monthly = txn_monthly + custom_monthly

c1, c2, c3 = st.columns(3)
c1.metric("From Transactions", f"${txn_monthly:,.2f}/mo")
c2.metric("Custom Sources", f"${custom_monthly:,.2f}/mo")
c3.metric("Total Monthly Income", f"${total_monthly:,.2f}/mo")

if total_monthly > 0:
    if st.button("Sync to Savings Projector", help="Updates the monthly income estimate used on the Savings page"):
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("UPDATE budgetlens.settings SET value = :v WHERE key = 'monthly_income_estimate'"),
                    {"v": str(round(total_monthly, 2))},
                )
            st.success(f"Savings projector updated to ${total_monthly:,.2f}/month.")
        except Exception as e:
            st.error(f"Sync failed: {e}")
