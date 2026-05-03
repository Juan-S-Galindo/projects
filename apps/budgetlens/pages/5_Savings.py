import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS
from src.projector import compute_projection, months_to_goal

st.set_page_config(page_title="Savings — BudgetLens", layout="wide")
st.title("🏦 Savings Projector")

# ── Load data ─────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        bills_df = pd.read_sql(
            text("SELECT * FROM budgetlens.bills WHERE active = TRUE"),
            conn,
        )
        goals_df = pd.read_sql(
            text("SELECT * FROM budgetlens.savings_goals ORDER BY target_date"),
            conn,
        )
        # Last 3 months average variable spending by category
        variable_df = pd.read_sql(
            text("""
                SELECT category, AVG(monthly_total) as avg_spend
                FROM (
                    SELECT category,
                           to_char(transaction_date, 'YYYY-MM') as month,
                           SUM(ABS(amount)) as monthly_total
                    FROM budgetlens.transactions_deduped
                    WHERE amount < 0
                      AND transaction_date >= CURRENT_DATE - INTERVAL '3 months'
                      AND category NOT IN ('transfer', 'income', 'mortgage', 'hoa', 'rent')
                    GROUP BY category, to_char(transaction_date, 'YYYY-MM')
                ) monthly
                GROUP BY category
                ORDER BY avg_spend DESC
            """),
            conn,
        )
        income_setting = conn.execute(
            text("SELECT value FROM budgetlens.settings WHERE key = 'monthly_income_estimate'")
        ).fetchone()
        monthly_income = float(income_setting[0]) if income_setting else 0.0
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# ── Income display ────────────────────────────────────────────────────────────

st.subheader("Monthly Income")
st.metric("Estimated Monthly Take-Home", f"${monthly_income:,.2f}")
st.caption("Configure income sources and cadence on the **Income** page.")

st.markdown("---")

# ── Projection breakdown ──────────────────────────────────────────────────────

total_bills = float(bills_df["monthly_equivalent"].sum()) if not bills_df.empty else 0.0
avg_variable = float(variable_df["avg_spend"].sum()) if not variable_df.empty else 0.0

# What-if adjustments
st.subheader("What-If Sliders")
st.caption("Adjust how much you cut from each spending category to see the impact on savings.")

what_if_cuts: dict[str, float] = {}
if not variable_df.empty:
    for _, row in variable_df.iterrows():
        cat = row["category"]
        current = float(row["avg_spend"])
        label = CATEGORY_LABELS.get(cat, cat)
        cut = st.slider(
            f"Cut {label} spending by:",
            min_value=0.0,
            max_value=float(current),
            value=0.0,
            step=5.0,
            format="$%.0f",
            key=f"slider_{cat}",
        )
        if cut > 0:
            what_if_cuts[cat] = cut
else:
    st.info("No spending data in the last 3 months. Import transactions to use the projector.")

proj = compute_projection(monthly_income, total_bills, avg_variable, what_if_cuts)

st.markdown("---")
st.subheader("Projection")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Monthly Income", f"${proj['monthly_income']:,.2f}")
col2.metric("Fixed Bills", f"${proj['total_monthly_bills']:,.2f}")
col3.metric("Variable Spending", f"${proj['avg_variable_spending']:,.2f}")
col4.metric(
    "Projected Savable",
    f"${proj['projected_savable']:,.2f}",
    delta=f"+${proj['total_cuts']:,.2f} from cuts" if proj["total_cuts"] > 0 else None,
)

if proj["total_cuts"] > 0:
    st.success(
        f"With your what-if cuts (${proj['total_cuts']:,.2f}/month), "
        f"you could save **${proj['adjusted_savable']:,.2f}/month**."
    )

st.markdown("---")

# ── Savings goals ─────────────────────────────────────────────────────────────

st.subheader("Savings Goals")

if goals_df.empty:
    st.info("No savings goals yet. Add one below.")
else:
    for _, g in goals_df.iterrows():
        target = float(g["target_amount"])
        current = float(g["current_amount"])
        pct = min(current / target, 1.0) if target > 0 else 0
        monthly_contrib = float(g["monthly_contribution"]) if g["monthly_contribution"] else proj["adjusted_savable"]
        months = months_to_goal(target, current, monthly_contrib)

        with st.expander(f"🎯 **{g['name']}** — ${current:,.2f} / ${target:,.2f}", expanded=True):
            st.progress(pct)
            c1, c2, c3 = st.columns(3)
            c1.metric("Target Amount", f"${target:,.2f}")
            c2.metric("Current Saved", f"${current:,.2f}")
            c3.metric("Target Date", str(g["target_date"]))

            if months is None:
                st.warning("Set a monthly contribution to see when you'll reach this goal.")
            elif months == 0:
                st.success("Goal reached! 🎉")
            else:
                st.info(f"At ${monthly_contrib:,.2f}/month, you'll reach this goal in **{months} months**.")

            update_col, del_col = st.columns([3, 1])
            with update_col:
                new_current = st.number_input(
                    "Update current saved ($)",
                    value=current,
                    min_value=0.0,
                    key=f"cur_{g['id']}",
                )
                new_contrib = st.number_input(
                    "Monthly contribution ($)",
                    value=monthly_contrib,
                    min_value=0.0,
                    key=f"contrib_{g['id']}",
                )
                if st.button("Update", key=f"upd_{g['id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("""
                                    UPDATE budgetlens.savings_goals
                                    SET current_amount = :cur, monthly_contribution = :contrib
                                    WHERE id = :id
                                """),
                                {"cur": new_current, "contrib": new_contrib, "id": str(g["id"])},
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")
            with del_col:
                if st.button("🗑️ Delete", key=f"gdel_{g['id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("DELETE FROM budgetlens.savings_goals WHERE id = :id"),
                                {"id": str(g["id"])},
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

# ── Add goal ───────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Add Savings Goal")

with st.form("add_goal_form"):
    c1, c2 = st.columns(2)
    with c1:
        goal_name = st.text_input("Goal name *", placeholder="e.g. Emergency Fund")
        goal_target = st.number_input("Target amount ($) *", min_value=1.0, step=100.0)
    with c2:
        goal_current = st.number_input("Amount already saved ($)", min_value=0.0, step=100.0)
        goal_date = st.date_input("Target date *", value=date(date.today().year + 1, 1, 1))

    goal_contrib = st.number_input(
        "Monthly contribution ($) — leave 0 to use projected savable",
        min_value=0.0,
        step=50.0,
    )

    if goal_target > 0 and goal_current < goal_target:
        effective_contrib = goal_contrib if goal_contrib > 0 else proj["adjusted_savable"]
        m = months_to_goal(goal_target, goal_current, effective_contrib)
        if m is not None and m > 0:
            st.info(f"At ${effective_contrib:,.2f}/month → **{m} months** to reach your goal.")

    submitted = st.form_submit_button("Add Goal", type="primary")

if submitted:
    if not goal_name:
        st.error("Goal name is required.")
    else:
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO budgetlens.savings_goals
                            (name, target_amount, target_date, current_amount, monthly_contribution)
                        VALUES (:name, :target, :date, :current, :contrib)
                    """),
                    {"name": goal_name, "target": goal_target, "date": goal_date,
                     "current": goal_current, "contrib": goal_contrib or None},
                )
            st.success(f"Goal **{goal_name}** added!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add goal: {e}")
