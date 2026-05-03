import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.db.schema import init_schema
from src.categorizer import CATEGORY_LABELS

st.set_page_config(
    page_title="BudgetLens",
    page_icon="💰",
    layout="wide",
)

# Initialize schema on first load
init_schema()

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "0") -> str:
    try:
        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT value FROM budgetlens.settings WHERE key = :k"),
                {"k": key},
            ).fetchone()
            return row[0] if row else default
    except Exception:
        return default


def fmt_currency(v: float) -> str:
    return f"${v:,.2f}"


# ── Month selector ────────────────────────────────────────────────────────────

today = date.today()
all_months = [
    date(today.year if today.month - i > 0 else today.year - 1,
         (today.month - i - 1) % 12 + 1, 1)
    for i in range(12)
]
month_options = {m.strftime("%B %Y"): m for m in all_months}

with st.sidebar:
    st.title("💰 BudgetLens")
    st.markdown("---")
    selected_label = st.selectbox("Month", list(month_options.keys()))
    selected_month = month_options[selected_label]
    month_str = selected_month.strftime("%Y-%m")
    st.markdown("---")
    st.page_link("pages/1_Import.py", label="📥 Import CSV", icon=None)
    st.page_link("pages/2_Transactions.py", label="📋 Transactions", icon=None)
    st.page_link("pages/3_Income.py", label="💰 Income", icon=None)
    st.page_link("pages/4_Bills.py", label="🧾 Bills", icon=None)
    st.page_link("pages/5_Budget.py", label="📊 Budget", icon=None)
    st.page_link("pages/6_Savings.py", label="🏦 Savings", icon=None)
    st.page_link("pages/7_Reports.py", label="📈 Reports", icon=None)

st.title(f"Dashboard — {selected_label}")

# ── Load data ─────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        txns = pd.read_sql(
            text("""
                SELECT * FROM budgetlens.transactions_deduped
                WHERE to_char(transaction_date, 'YYYY-MM') = :m
            """),
            conn,
            params={"m": month_str},
        )
        budgets = pd.read_sql(text("SELECT * FROM budgetlens.budget_categories"), conn)
        bills = pd.read_sql(
            text("SELECT * FROM budgetlens.bills WHERE active = TRUE"), conn
        )
        goals = pd.read_sql(text("SELECT * FROM budgetlens.savings_goals"), conn)

    db_ok = True
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.info("Make sure PostgreSQL is running and PGHOST / PGUSER / PGPASSWORD env vars are set.")
    st.stop()
    db_ok = False

# ── Monthly snapshot ──────────────────────────────────────────────────────────

income = float(txns[txns["amount"] > 0]["amount"].sum()) if not txns.empty else 0.0
spending = float(txns[txns["amount"] < 0]["amount"].sum()) if not txns.empty else 0.0
net_saved = income + spending  # spending is negative

col1, col2, col3 = st.columns(3)
col1.metric("Total Income", fmt_currency(income))
col2.metric("Total Spending", fmt_currency(abs(spending)))
delta_color = "normal" if net_saved >= 0 else "inverse"
col3.metric("Net Saved", fmt_currency(net_saved), delta=None)

st.markdown("---")

# ── Alerts ────────────────────────────────────────────────────────────────────

alert_threshold = float(get_setting("alert_threshold_percent", "80")) / 100

if not txns.empty and not budgets.empty:
    spend_by_cat = (
        txns[txns["amount"] < 0]
        .groupby("category")["amount"]
        .sum()
        .abs()
    )
    for _, brow in budgets.iterrows():
        cat = brow["category_id"]
        limit = float(brow["monthly_limit"])
        spent = float(spend_by_cat.get(cat, 0))
        pct = spent / limit if limit > 0 else 0
        if pct >= alert_threshold:
            label = CATEGORY_LABELS.get(cat, cat)
            st.warning(
                f"⚠️ **{label}**: ${spent:,.2f} spent of ${limit:,.2f} limit "
                f"({pct:.0%}) — {'over budget!' if pct > 1 else 'approaching limit'}"
            )

# Overdue bills
if not bills.empty:
    today_date = date.today()
    overdue = bills[
        bills["next_charge_date"].notna()
        & (pd.to_datetime(bills["next_charge_date"]).dt.date < today_date)
    ]
    for _, b in overdue.iterrows():
        st.error(f"🔴 **Bill overdue**: {b['name']} — was due {b['next_charge_date']}")

st.markdown("---")

# ── Budget health ─────────────────────────────────────────────────────────────

st.subheader("Budget Health")

if budgets.empty:
    st.info("No budgets configured yet. Go to **Budget** to set monthly limits.")
else:
    spend_by_cat = {}
    if not txns.empty:
        spend_by_cat = (
            txns[txns["amount"] < 0]
            .groupby("category")["amount"]
            .sum()
            .abs()
            .to_dict()
        )

    cols = st.columns(min(len(budgets), 3))
    for i, (_, brow) in enumerate(budgets.iterrows()):
        cat = brow["category_id"]
        limit = float(brow["monthly_limit"])
        spent = float(spend_by_cat.get(cat, 0))
        pct = min(spent / limit, 1.0) if limit > 0 else 0
        label = CATEGORY_LABELS.get(cat, cat)
        color = "#EF4444" if pct > 1 else "#F59E0B" if pct >= alert_threshold else "#22C55E"
        with cols[i % 3]:
            st.markdown(f"**{label}**")
            st.progress(pct)
            st.caption(f"{fmt_currency(spent)} / {fmt_currency(limit)}")

st.markdown("---")

# ── Savings goals ──────────────────────────────────────────────────────────────

st.subheader("Savings Goals")

if goals.empty:
    st.info("No savings goals yet. Go to **Savings** to add one.")
else:
    for _, g in goals.iterrows():
        target = float(g["target_amount"])
        current = float(g["current_amount"])
        pct = min(current / target, 1.0) if target > 0 else 0
        st.markdown(f"**{g['name']}** — {fmt_currency(current)} / {fmt_currency(target)}")
        st.progress(pct)
        st.caption(f"Target date: {g['target_date']}")

st.markdown("---")

# ── Spending donut preview ────────────────────────────────────────────────────

if not txns.empty:
    expenses = txns[txns["amount"] < 0].copy()
    if not expenses.empty:
        by_cat = expenses.groupby("category")["amount"].sum().abs().reset_index()
        by_cat["label"] = by_cat["category"].map(lambda c: CATEGORY_LABELS.get(c, c))
        fig = go.Figure(go.Pie(
            labels=by_cat["label"],
            values=by_cat["amount"],
            hole=0.4,
            textinfo="label+percent",
        ))
        fig.update_layout(
            title=f"Spending by Category — {selected_label}",
            showlegend=False,
            margin=dict(t=40, b=0, l=0, r=0),
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)
