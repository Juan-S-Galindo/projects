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
    "semi_monthly": {"label": "Semi-Monthly", "per_year": 24},
    "biweekly":     {"label": "Biweekly",     "per_year": 26},
}


def monthly_from_cadence(amount: float, cadence: str) -> float:
    return amount * CADENCE_OPTIONS[cadence]["per_year"] / 12


# ── Load ──────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        cadence_row = conn.execute(
            text("SELECT value FROM budgetlens.settings WHERE key = 'pay_cadence'")
        ).fetchone()
        default_cadence = cadence_row[0] if cadence_row else "semi_monthly"

        income_txns = pd.read_sql(
            text("""
                SELECT
                    content_hash,
                    description,
                    transaction_date,
                    amount
                FROM budgetlens.transactions_deduped
                WHERE category = 'income'
                  AND amount > 0
                ORDER BY description, transaction_date DESC
            """),
            conn,
        )

        excluded_set = set(
            pd.read_sql(
                text("SELECT content_hash FROM budgetlens.income_excluded_hashes"),
                conn,
            )["content_hash"].tolist()
        )

        rules_raw = pd.read_sql(
            text("SELECT * FROM budgetlens.income_transaction_rules"),
            conn,
        )

        sources_df = pd.read_sql(
            text("SELECT * FROM budgetlens.income_sources ORDER BY name"),
            conn,
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

rules: dict[str, dict] = {}
if not rules_raw.empty:
    for _, r in rules_raw.iterrows():
        rules[r["description"]] = {
            "name_override":   r.get("name_override"),
            "cadence":         r.get("cadence"),
            "amount_override": r.get("amount_override"),
        }

# ── Pay Cadence ───────────────────────────────────────────────────────────────

st.subheader("Pay Cadence")
st.caption("Default cadence applied to income sources that don't have their own setting.")

new_cadence = st.selectbox(
    "Default Cadence",
    list(CADENCE_OPTIONS.keys()),
    index=list(CADENCE_OPTIONS.keys()).index(default_cadence),
    format_func=lambda c: CADENCE_OPTIONS[c]["label"],
    key="default_cadence_select",
)
if new_cadence != default_cadence:
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE budgetlens.settings SET value = :v WHERE key = 'pay_cadence'"),
                {"v": new_cadence},
            )
        default_cadence = new_cadence
        st.success("Default cadence updated.")
    except Exception as e:
        st.error(f"Failed to save: {e}")

st.markdown("---")

# ── Income Sources from Transactions ─────────────────────────────────────────

st.subheader("Income Sources")

total_monthly_txns = 0.0

if income_txns.empty:
    st.info("No income transactions found. Import transactions categorized as income to see sources here.")
else:
    income_txns["included"] = ~income_txns["content_hash"].isin(excluded_set)

    for idx, (desc, group) in enumerate(income_txns.groupby("description")):
        group = group.reset_index(drop=True)
        rule = rules.get(desc, {})
        name = rule.get("name_override") or desc
        cadence = rule.get("cadence") or default_cadence
        amount_override = rule.get("amount_override")

        included_amounts = group.loc[group["included"], "amount"]
        avg_amt = float(included_amounts.mean()) if not included_amounts.empty else 0.0
        effective_amt = float(amount_override) if amount_override is not None else avg_amt
        monthly = monthly_from_cadence(effective_amt, cadence)
        total_monthly_txns += monthly

        cadence_label = CADENCE_OPTIONS[cadence]["label"]

        with st.expander(
            f"💵 **{name}**  —  ${effective_amt:,.2f} {cadence_label}  →  "
            f"**${monthly:,.2f}/month**",
            expanded=False,
        ):
            st.markdown("**Transactions** — uncheck to exclude from the average")

            txn_display = group[["transaction_date", "amount", "included"]].copy()
            txn_display["transaction_date"] = txn_display["transaction_date"].astype(str)
            txn_display["amount"] = txn_display["amount"].astype(float)
            txn_display = txn_display.rename(columns={
                "transaction_date": "Date",
                "amount": "Amount ($)",
                "included": "Include",
            })

            edited = st.data_editor(
                txn_display,
                column_config={
                    "Date": st.column_config.TextColumn(disabled=True, width="small"),
                    "Amount ($)": st.column_config.NumberColumn(
                        disabled=True, format="$%.2f", width="small"
                    ),
                    "Include": st.column_config.CheckboxColumn(width="small"),
                },
                hide_index=True,
                use_container_width=True,
                key=f"txn_editor_{idx}",
            )

            include_mask = edited["Include"].values
            live_avg = float(group.loc[include_mask, "amount"].mean()) if include_mask.any() else 0.0

            st.markdown("---")
            st.markdown("**Source Settings**")

            s1, s2 = st.columns(2)
            with s1:
                new_name = st.text_input(
                    "Display name", value=name, key=f"inc_name_{idx}"
                )
                new_src_cadence = st.selectbox(
                    "Cadence",
                    list(CADENCE_OPTIONS.keys()),
                    index=list(CADENCE_OPTIONS.keys()).index(cadence),
                    format_func=lambda c: CADENCE_OPTIONS[c]["label"],
                    key=f"inc_cad_{idx}",
                )
            with s2:
                use_override = st.checkbox(
                    "Override calculated average",
                    value=amount_override is not None,
                    key=f"inc_ovr_toggle_{idx}",
                )
                new_override = None
                if use_override:
                    new_override = st.number_input(
                        "Override amount per check ($)",
                        value=float(amount_override) if amount_override is not None else live_avg,
                        min_value=0.01,
                        key=f"inc_ovr_{idx}",
                    )

            display_amt = new_override if use_override and new_override else live_avg
            new_monthly = monthly_from_cadence(display_amt, new_src_cadence)
            st.info(
                f"Avg from **{int(include_mask.sum())}** selected transaction(s): **${live_avg:,.2f}**  ·  "
                f"Monthly equivalent: **${new_monthly:,.2f}/month**"
            )

            if st.button("💾 Save", type="primary", key=f"inc_save_{idx}"):
                try:
                    with get_engine().begin() as conn:
                        group_hashes = group["content_hash"].tolist()
                        conn.execute(
                            text("""
                                DELETE FROM budgetlens.income_excluded_hashes
                                WHERE content_hash = ANY(:hashes)
                            """),
                            {"hashes": group_hashes},
                        )
                        newly_excluded = group.loc[~pd.Series(include_mask, index=group.index), "content_hash"].tolist()
                        if newly_excluded:
                            conn.execute(
                                text("""
                                    INSERT INTO budgetlens.income_excluded_hashes (content_hash)
                                    SELECT unnest(:hashes::text[])
                                    ON CONFLICT DO NOTHING
                                """),
                                {"hashes": newly_excluded},
                            )
                        conn.execute(
                            text("""
                                INSERT INTO budgetlens.income_transaction_rules
                                    (description, is_regular, name_override, cadence, amount_override)
                                VALUES (:desc, TRUE, :name, :cad, :ovr)
                                ON CONFLICT (description) DO UPDATE SET
                                    name_override   = EXCLUDED.name_override,
                                    cadence         = EXCLUDED.cadence,
                                    amount_override = EXCLUDED.amount_override
                            """),
                            {
                                "desc": desc,
                                "name": new_name if new_name != desc else None,
                                "cad":  new_src_cadence,
                                "ovr":  new_override,
                            },
                        )
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

st.markdown("---")

# ── Custom Income Sources ─────────────────────────────────────────────────────

st.subheader("Custom Income Sources")
st.caption("Add income not captured in your bank transactions (freelance, rental, etc.).")

if not sources_df.empty:
    for _, src in sources_df.iterrows():
        src_monthly = monthly_from_cadence(float(src["amount"]), src["cadence"])
        cadence_label = CADENCE_OPTIONS.get(src["cadence"], {}).get("label", src["cadence"])
        active_label = "" if src["active"] else " *(inactive)*"

        with st.expander(
            f"✏️ **{src['name']}**{active_label}  —  "
            f"${float(src['amount']):,.2f} {cadence_label}  →  **${src_monthly:,.2f}/month**",
            expanded=False,
        ):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                new_src_name = st.text_input("Name", value=src["name"], key=f"sname_{src['id']}")
            with ec2:
                new_src_amount = st.number_input(
                    "Amount ($)", value=float(src["amount"]), min_value=0.01, key=f"samt_{src['id']}"
                )
            with ec3:
                new_src_cad = st.selectbox(
                    "Cadence",
                    list(CADENCE_OPTIONS.keys()),
                    index=list(CADENCE_OPTIONS.keys()).index(src["cadence"])
                    if src["cadence"] in CADENCE_OPTIONS else 1,
                    format_func=lambda c: CADENCE_OPTIONS[c]["label"],
                    key=f"scad_{src['id']}",
                )

            new_src_monthly = monthly_from_cadence(new_src_amount, new_src_cad)
            st.info(f"Monthly equivalent: **${new_src_monthly:,.2f}/month**")
            new_src_active = st.checkbox("Active", value=bool(src["active"]), key=f"sact_{src['id']}")

            dc1, dc2 = st.columns([1, 1])
            with dc1:
                if st.button("Save", key=f"ssave_{src['id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("""
                                    UPDATE budgetlens.income_sources
                                    SET name = :name, amount = :amt, cadence = :cad, active = :active
                                    WHERE id = :id
                                """),
                                {"name": new_src_name, "amt": new_src_amount,
                                 "cad": new_src_cad, "active": new_src_active,
                                 "id": str(src["id"])},
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")
            with dc2:
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
    add_amount = st.number_input(
        "Amount per paycheck ($) *", min_value=0.01, step=100.0, key="add_src_amount"
    )
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

custom_monthly = 0.0
if not sources_df.empty:
    for _, src in sources_df[sources_df["active"] == True].iterrows():
        custom_monthly += monthly_from_cadence(float(src["amount"]), src["cadence"])

total_monthly = total_monthly_txns + custom_monthly

c1, c2, c3 = st.columns(3)
c1.metric("From Transactions", f"${total_monthly_txns:,.2f}/mo")
c2.metric("Custom Sources", f"${custom_monthly:,.2f}/mo")
c3.metric("Total Monthly Income", f"${total_monthly:,.2f}/mo")

if total_monthly > 0:
    if st.button("Sync to Savings Projector"):
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("UPDATE budgetlens.settings SET value = :v WHERE key = 'monthly_income_estimate'"),
                    {"v": str(round(total_monthly, 2))},
                )
            st.success(f"Savings projector updated to ${total_monthly:,.2f}/month.")
        except Exception as e:
            st.error(f"Sync failed: {e}")
