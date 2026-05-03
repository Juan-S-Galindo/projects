import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import CATEGORY_LABELS

st.set_page_config(page_title="Reports — BudgetLens", layout="wide")
st.title("📈 Reports & Charts")

# ── Date range ─────────────────────────────────────────────────────────────────

col1, col2 = st.columns([1, 3])
with col1:
    months_back = st.selectbox("History", [3, 6, 12], index=1, format_func=lambda v: f"Last {v} months")

# ── Load data ──────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        monthly_df = pd.read_sql(
            text("""
                SELECT
                    to_char(transaction_date, 'YYYY-MM') AS month,
                    category,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) AS spending,
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END)       AS income
                FROM budgetlens.transactions
                WHERE transaction_date >= CURRENT_DATE - (:m * INTERVAL '1 month')
                GROUP BY 1, 2
                ORDER BY 1, 2
            """),
            conn,
            params={"m": months_back},
        )
        budgets_df = pd.read_sql(
            text("SELECT category_id, monthly_limit FROM budgetlens.budget_categories"),
            conn,
        )
        this_month = date.today().strftime("%Y-%m")
        this_month_df = pd.read_sql(
            text("""
                SELECT category, SUM(ABS(amount)) as spent
                FROM budgetlens.transactions
                WHERE amount < 0
                  AND to_char(transaction_date, 'YYYY-MM') = :m
                GROUP BY category
            """),
            conn,
            params={"m": this_month},
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

if monthly_df.empty:
    st.info("No transaction data yet. Import CSV files to see reports.")
    st.stop()

monthly_df["month_label"] = monthly_df["month"]
monthly_df["cat_label"] = monthly_df["category"].map(lambda c: CATEGORY_LABELS.get(c, c))

# ── 1. Spending by category — donut ─────────────────────────────────────────────

st.subheader(f"Spending by Category — Last {months_back} Months")

cat_total = (
    monthly_df[monthly_df["spending"] > 0]
    .groupby("cat_label")["spending"]
    .sum()
    .reset_index()
    .sort_values("spending", ascending=False)
)

fig_pie = go.Figure(go.Pie(
    labels=cat_total["cat_label"],
    values=cat_total["spending"],
    hole=0.4,
    textinfo="label+percent",
    hovertemplate="%{label}: $%{value:,.2f}<extra></extra>",
))
fig_pie.update_layout(
    showlegend=True,
    margin=dict(t=20, b=20, l=0, r=0),
    height=400,
)
st.plotly_chart(fig_pie, use_container_width=True)

st.markdown("---")

# ── 2. Monthly trend by category — stacked bar ────────────────────────────────

st.subheader("Monthly Spending Trend by Category")

pivot = monthly_df[monthly_df["spending"] > 0].pivot_table(
    index="month_label", columns="cat_label", values="spending", aggfunc="sum", fill_value=0
).reset_index()

fig_bar = go.Figure()
# Top 8 categories by total spend to keep chart readable
top_cats = cat_total.head(8)["cat_label"].tolist()
colors = px.colors.qualitative.Set2

for i, cat in enumerate(top_cats):
    if cat in pivot.columns:
        fig_bar.add_trace(go.Bar(
            x=pivot["month_label"],
            y=pivot[cat],
            name=cat,
            marker_color=colors[i % len(colors)],
            hovertemplate=f"{cat}: $%{{y:,.2f}}<extra></extra>",
        ))

fig_bar.update_layout(
    barmode="stack",
    xaxis_title="Month",
    yaxis_title="Spending ($)",
    legend_title="Category",
    height=400,
    margin=dict(t=20, b=20),
)
st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ── 3. Budget vs. actual — this month ─────────────────────────────────────────

if not budgets_df.empty and not this_month_df.empty:
    st.subheader(f"Budget vs. Actual — {date.today().strftime('%B %Y')}")

    merged = budgets_df.merge(
        this_month_df,
        left_on="category_id",
        right_on="category",
        how="left",
    ).fillna(0)
    merged["label"] = merged["category_id"].map(lambda c: CATEGORY_LABELS.get(c, c))
    merged["spent"] = merged["spent"].astype(float)
    merged["monthly_limit"] = merged["monthly_limit"].astype(float)

    fig_bva = go.Figure()
    fig_bva.add_trace(go.Bar(
        x=merged["label"],
        y=merged["monthly_limit"],
        name="Budget Limit",
        marker_color="#93C5FD",
        hovertemplate="Budget: $%{y:,.2f}<extra></extra>",
    ))
    fig_bva.add_trace(go.Bar(
        x=merged["label"],
        y=merged["spent"],
        name="Actual Spend",
        marker_color=["#EF4444" if s > l else "#22C55E"
                      for s, l in zip(merged["spent"], merged["monthly_limit"])],
        hovertemplate="Spent: $%{y:,.2f}<extra></extra>",
    ))
    fig_bva.update_layout(
        barmode="group",
        xaxis_title="Category",
        yaxis_title="Amount ($)",
        height=400,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_bva, use_container_width=True)
    st.markdown("---")

# ── 4. Net savings over time — area chart ─────────────────────────────────────

st.subheader("Net Savings Over Time")

net_by_month = (
    monthly_df
    .groupby("month_label")
    .agg(income=("income", "sum"), spending=("spending", "sum"))
    .reset_index()
)
net_by_month["net"] = net_by_month["income"] - net_by_month["spending"]
net_by_month["color"] = net_by_month["net"].apply(lambda v: "#22C55E" if v >= 0 else "#EF4444")

fig_net = go.Figure()
fig_net.add_trace(go.Scatter(
    x=net_by_month["month_label"],
    y=net_by_month["income"],
    mode="lines+markers",
    name="Income",
    line=dict(color="#2563EB", width=2),
    hovertemplate="Income: $%{y:,.2f}<extra></extra>",
))
fig_net.add_trace(go.Scatter(
    x=net_by_month["month_label"],
    y=net_by_month["spending"],
    mode="lines+markers",
    name="Spending",
    line=dict(color="#DC2626", width=2),
    hovertemplate="Spending: $%{y:,.2f}<extra></extra>",
))
fig_net.add_trace(go.Scatter(
    x=net_by_month["month_label"],
    y=net_by_month["net"],
    mode="lines+markers",
    name="Net Saved",
    line=dict(color="#16A34A", width=2, dash="dot"),
    fill="tozeroy",
    fillcolor="rgba(22,163,74,0.1)",
    hovertemplate="Net: $%{y:,.2f}<extra></extra>",
))
fig_net.update_layout(
    xaxis_title="Month",
    yaxis_title="Amount ($)",
    legend_title="",
    height=400,
    margin=dict(t=20, b=20),
    hovermode="x unified",
)
st.plotly_chart(fig_net, use_container_width=True)

st.markdown("---")

# ── 5. Raw data table ──────────────────────────────────────────────────────────

with st.expander("📄 Raw monthly data"):
    st.dataframe(net_by_month.rename(columns={
        "month_label": "Month",
        "income": "Income ($)",
        "spending": "Spending ($)",
        "net": "Net Saved ($)",
    }).drop(columns=["color"]), use_container_width=True)
