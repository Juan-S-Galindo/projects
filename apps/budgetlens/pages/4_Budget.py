import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS

st.set_page_config(page_title="Budget — BudgetLens", layout="wide")
st.title("📊 Budget Manager")

today = date.today()
month_str = today.strftime("%Y-%m")

# ── Load ────────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        budgets = pd.read_sql(
            text("SELECT * FROM budgetlens.budget_categories ORDER BY category_id"),
            conn,
        )
        spend_df = pd.read_sql(
            text("""
                SELECT category, SUM(ABS(amount)) as spent
                FROM budgetlens.transactions
                WHERE amount < 0
                  AND to_char(transaction_date, 'YYYY-MM') = :m
                GROUP BY category
            """),
            conn,
            params={"m": month_str},
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

spend_by_cat = dict(zip(spend_df["category"], spend_df["spent"])) if not spend_df.empty else {}

# ── Existing budgets ─────────────────────────────────────────────────────────

st.subheader(f"Budget vs. Actual — {today.strftime('%B %Y')}")

if budgets.empty:
    st.info("No budget categories configured yet. Add one below.")
else:
    total_limit = float(budgets["monthly_limit"].sum())
    total_spent = sum(float(spend_by_cat.get(row["category_id"], 0)) for _, row in budgets.iterrows())
    overall_pct = total_spent / total_limit if total_limit > 0 else 0
    st.markdown(f"**Overall:** ${total_spent:,.2f} / ${total_limit:,.2f} ({overall_pct:.0%})")
    st.progress(min(overall_pct, 1.0))
    st.markdown("---")

    # Fixed vs variable split
    fixed_budgets = budgets[budgets["budget_type"] == "fixed"]
    variable_budgets = budgets[budgets["budget_type"] == "variable"]

    for section_label, section_df in [("Fixed Expenses", fixed_budgets), ("Variable Expenses", variable_budgets)]:
        if section_df.empty:
            continue
        st.markdown(f"### {section_label}")
        cols = st.columns(3)
        for i, (_, brow) in enumerate(section_df.iterrows()):
            cat = brow["category_id"]
            limit = float(brow["monthly_limit"])
            spent = float(spend_by_cat.get(cat, 0))
            pct = min(spent / limit, 1.0) if limit > 0 else 0
            label = CATEGORY_LABELS.get(cat, cat)
            rollover_note = " 🔄" if brow["rollover"] else ""

            with cols[i % 3]:
                st.markdown(f"**{label}{rollover_note}**")
                bar_color = "red" if pct > 1 else ("orange" if pct >= 0.8 else "green")
                # Streamlit progress doesn't support custom colors, show with caption
                st.progress(pct)
                st.caption(f"${spent:,.2f} / ${limit:,.2f} ({pct:.0%})")

                edit_col, del_col = st.columns(2)
                with edit_col:
                    if st.button("Edit", key=f"bedit_{brow['id']}"):
                        st.session_state["editing_budget"] = str(brow["id"])
                with del_col:
                    if st.button("Delete", key=f"bdel_{brow['id']}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("DELETE FROM budgetlens.budget_categories WHERE id = :id"),
                                    {"id": str(brow["id"])},
                                )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

# ── Edit budget ───────────────────────────────────────────────────────────────

if "editing_budget" in st.session_state and not budgets.empty:
    eid = st.session_state["editing_budget"]
    erow = budgets[budgets["id"].astype(str) == eid]
    if not erow.empty:
        b = erow.iloc[0]
        st.markdown("---")
        st.subheader(f"Edit: {CATEGORY_LABELS.get(b['category_id'], b['category_id'])}")
        with st.form("edit_budget_form"):
            new_limit = st.number_input("Monthly limit ($)", value=float(b["monthly_limit"]), min_value=0.01)
            new_rollover = st.checkbox("Rollover unused budget to next month", value=bool(b["rollover"]))
            new_type = st.radio("Budget type", ["variable", "fixed"],
                                index=0 if b["budget_type"] == "variable" else 1)
            save = st.form_submit_button("Save")
        if save:
            try:
                with get_engine().begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE budgetlens.budget_categories
                            SET monthly_limit = :limit, rollover = :rollover, budget_type = :btype
                            WHERE id = :id
                        """),
                        {"limit": new_limit, "rollover": new_rollover,
                         "btype": new_type, "id": eid},
                    )
                del st.session_state["editing_budget"]
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

# ── Add new budget category ────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Add Budget Category")

existing_cats = set(budgets["category_id"].tolist()) if not budgets.empty else set()
available_cats = [c for c in ALL_CATEGORIES if c not in existing_cats]

if not available_cats:
    st.info("All categories already have a budget configured.")
else:
    with st.form("add_budget_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            cat = st.selectbox(
                "Category",
                available_cats,
                format_func=lambda c: CATEGORY_LABELS.get(c, c),
            )
        with c2:
            limit = st.number_input("Monthly limit ($)", min_value=1.0, step=10.0)
        with c3:
            btype = st.radio("Type", ["variable", "fixed"])

        rollover = st.checkbox("Rollover unused budget to next month")
        submitted = st.form_submit_button("Add Budget", type="primary")

    if submitted:
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO budgetlens.budget_categories
                            (category_id, monthly_limit, rollover, budget_type)
                        VALUES (:cat, :limit, :rollover, :btype)
                        ON CONFLICT (category_id) DO UPDATE
                            SET monthly_limit = EXCLUDED.monthly_limit,
                                rollover = EXCLUDED.rollover,
                                budget_type = EXCLUDED.budget_type
                    """),
                    {"cat": cat, "limit": limit, "rollover": rollover, "btype": btype},
                )
            st.success(f"Budget added for **{CATEGORY_LABELS.get(cat, cat)}**: ${limit:,.2f}/month")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add budget: {e}")
