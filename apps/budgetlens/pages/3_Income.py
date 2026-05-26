import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
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

FILTER_TYPES = {
    "contains":    "Contains",
    "starts_with": "Starts With",
    "regex":       "Regex",
}


def monthly_from_cadence(amount: float, cadence: str) -> float:
    return amount * CADENCE_OPTIONS[cadence]["per_year"] / 12


def apply_filter(df: pd.DataFrame, filter_type: str, filter_value: str) -> pd.DataFrame:
    if not filter_value:
        return df.iloc[0:0]
    try:
        if filter_type == "contains":
            mask = df["description"].str.contains(filter_value, case=False, na=False)
        elif filter_type == "starts_with":
            mask = df["description"].str.startswith(filter_value, na=False)
        else:
            mask = df["description"].str.contains(filter_value, regex=True, case=False, na=False)
        return df[mask]
    except re.error:
        return df.iloc[0:0]


# ── Load ──────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        cadence_row = conn.execute(
            text("SELECT value FROM budgetlens.settings WHERE key = 'pay_cadence'")
        ).fetchone()
        default_cadence = cadence_row[0] if cadence_row else "semi_monthly"

        txns_all = pd.read_sql(
            text("""
                SELECT content_hash, description, transaction_date, amount
                FROM budgetlens.transactions_deduped
                WHERE amount > 0
                ORDER BY transaction_date DESC
            """),
            conn,
        )

        sources_df = pd.read_sql(
            text("SELECT * FROM budgetlens.income_transaction_sources ORDER BY alias"),
            conn,
        )

        excluded_df = pd.read_sql(
            text("SELECT source_id::text, content_hash FROM budgetlens.income_source_excluded_hashes"),
            conn,
        )

        entities = pd.read_sql(
            text("SELECT id, name, is_default FROM budgetlens.entities ORDER BY is_default DESC, name"),
            conn,
        )

        custom_sources_df = pd.read_sql(
            text("SELECT * FROM budgetlens.income_sources ORDER BY name"),
            conn,
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

entity_map = {str(r["id"]): r["name"] for _, r in entities.iterrows()}
entity_options = [None] + [str(r["id"]) for _, r in entities.iterrows()]
entity_labels = {None: "— No entity —", **entity_map}
default_entity_id = next(
    (str(r["id"]) for _, r in entities.iterrows() if r["is_default"]), None
)

excluded_by_source: dict[str, set[str]] = {}
if not excluded_df.empty:
    for sid, grp in excluded_df.groupby("source_id"):
        excluded_by_source[sid] = set(grp["content_hash"].tolist())


# ── Default Pay Cadence ───────────────────────────────────────────────────────

st.subheader("Default Pay Cadence")
st.caption("Applied to income sources that don't have their own cadence set.")

new_default_cadence = st.selectbox(
    "Default Cadence",
    list(CADENCE_OPTIONS.keys()),
    index=list(CADENCE_OPTIONS.keys()).index(default_cadence),
    format_func=lambda c: CADENCE_OPTIONS[c]["label"],
    key="default_cadence_select",
)
if new_default_cadence != default_cadence:
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE budgetlens.settings SET value = :v WHERE key = 'pay_cadence'"),
                {"v": new_default_cadence},
            )
        default_cadence = new_default_cadence
        st.success("Default cadence updated.")
    except Exception as e:
        st.error(f"Failed to save: {e}")

st.markdown("---")


# ── Source card renderer ───────────────────────────────────────────────────────

def render_txn_source(src) -> float:
    """Render an income source card and return its monthly contribution."""
    src_id = str(src["id"])
    filter_type = src.get("filter_type") or "contains"
    filter_value = src.get("filter_value") or ""
    cadence = src.get("cadence") or default_cadence
    amount_override = src.get("amount_override")
    cur_entity = str(src["entity_id"]) if src.get("entity_id") and not pd.isna(src.get("entity_id")) else None

    matched = apply_filter(txns_all, filter_type, filter_value) if filter_value else pd.DataFrame()
    excluded_hashes = excluded_by_source.get(src_id, set())

    if not matched.empty:
        matched_reset = matched.reset_index(drop=True)
        included_mask_stored = ~matched_reset["content_hash"].isin(excluded_hashes)
        included_amounts = matched_reset.loc[included_mask_stored, "amount"]
        live_avg = float(included_amounts.mean()) if not included_amounts.empty else 0.0
    else:
        matched_reset = pd.DataFrame()
        included_mask_stored = pd.Series([], dtype=bool)
        live_avg = 0.0

    effective_amt = float(amount_override) if amount_override is not None else live_avg
    monthly = monthly_from_cadence(effective_amt, cadence)
    cadence_label = CADENCE_OPTIONS.get(cadence, CADENCE_OPTIONS["semi_monthly"])["label"]
    active_label = "" if src["active"] else " *(inactive)*"

    with st.expander(
        f"💵 **{src['alias']}**{active_label}  —  "
        f"${effective_amt:,.2f} {cadence_label}  →  **${monthly:,.2f}/month**"
        + (f"  ({len(matched_reset)} transaction(s) matched)" if filter_value else ""),
        expanded=False,
    ):
        txn_edited = None
        inc_mask = []

        if filter_value:
            st.markdown("**Matched Transactions** — uncheck to exclude from the average")
            if matched_reset.empty:
                st.caption("No transactions match this filter.")
            else:
                txn_display = matched_reset[["transaction_date", "description", "amount"]].copy()
                txn_display["transaction_date"] = txn_display["transaction_date"].astype(str)
                txn_display["amount"] = txn_display["amount"].astype(float)
                txn_display["Include"] = included_mask_stored.values
                txn_display = txn_display.rename(columns={
                    "transaction_date": "Date",
                    "description": "Description",
                    "amount": "Amount ($)",
                })
                txn_edited = st.data_editor(
                    txn_display,
                    column_config={
                        "Date": st.column_config.TextColumn(disabled=True, width="small"),
                        "Description": st.column_config.TextColumn(disabled=True, width="large"),
                        "Amount ($)": st.column_config.NumberColumn(disabled=True, format="$%.2f", width="small"),
                        "Include": st.column_config.CheckboxColumn(width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"src_txns_{src_id}",
                )
                inc_mask = txn_edited["Include"].values
                if inc_mask.any():
                    live_avg = float(matched_reset.loc[inc_mask, "amount"].mean())
                else:
                    live_avg = 0.0

        st.markdown("---")
        st.markdown("**Source Settings**")

        s1, s2, s3 = st.columns(3)
        with s1:
            new_alias = st.text_input("Alias", value=src["alias"], key=f"src_alias_{src_id}")
            new_entity = st.selectbox(
                "Entity",
                entity_options,
                index=entity_options.index(cur_entity) if cur_entity in entity_options else 0,
                format_func=lambda eid: entity_labels.get(eid, "— No entity —"),
                key=f"src_entity_{src_id}",
            )
        with s2:
            new_filter_type = st.selectbox(
                "Filter type",
                list(FILTER_TYPES.keys()),
                index=list(FILTER_TYPES.keys()).index(filter_type) if filter_type in FILTER_TYPES else 0,
                format_func=lambda t: FILTER_TYPES[t],
                key=f"src_ftype_{src_id}",
            )
            new_filter_value = st.text_input(
                "Filter value", value=filter_value, key=f"src_fval_{src_id}"
            )
            new_cadence = st.selectbox(
                "Cadence",
                list(CADENCE_OPTIONS.keys()),
                index=list(CADENCE_OPTIONS.keys()).index(cadence) if cadence in CADENCE_OPTIONS else 1,
                format_func=lambda c: CADENCE_OPTIONS[c]["label"],
                key=f"src_cad_{src_id}",
            )
        with s3:
            use_override = st.checkbox(
                "Override calculated average",
                value=amount_override is not None,
                key=f"src_ovr_toggle_{src_id}",
            )
            new_override = None
            if use_override:
                new_override = st.number_input(
                    "Override amount per paycheck ($)",
                    value=float(amount_override) if amount_override is not None else max(live_avg, 0.01),
                    min_value=0.01,
                    key=f"src_ovr_{src_id}",
                )
            new_active = st.checkbox("Active", value=bool(src["active"]), key=f"src_active_{src_id}")

        display_amt = new_override if (use_override and new_override) else live_avg
        new_monthly = monthly_from_cadence(display_amt, new_cadence)
        if inc_mask is not None and len(inc_mask) > 0:
            st.info(
                f"{int(sum(inc_mask))} selected  ·  avg ${live_avg:,.2f}  ·  "
                f"→ **${new_monthly:,.2f}/month**"
            )
        else:
            st.info(f"Monthly equivalent: **${new_monthly:,.2f}/month**")

        sc1, sc2 = st.columns([1, 1])
        with sc1:
            if st.button("💾 Save", type="primary", key=f"src_save_{src_id}"):
                try:
                    with get_engine().begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE budgetlens.income_transaction_sources
                                SET alias = :alias, filter_type = :ftype, filter_value = :fval,
                                    cadence = :cad, amount_override = :ovr,
                                    active = :active, entity_id = :eid
                                WHERE id = :id
                            """),
                            {"alias": new_alias, "ftype": new_filter_type,
                             "fval": new_filter_value or None, "cad": new_cadence,
                             "ovr": new_override, "active": new_active,
                             "eid": new_entity, "id": src_id},
                        )
                        if txn_edited is not None and not matched_reset.empty:
                            group_hashes = matched_reset["content_hash"].tolist()
                            conn.execute(
                                text("""
                                    DELETE FROM budgetlens.income_source_excluded_hashes
                                    WHERE source_id = :sid AND content_hash = ANY(:hashes)
                                """),
                                {"sid": src_id, "hashes": group_hashes},
                            )
                            for h in matched_reset.loc[~pd.Series(inc_mask, index=matched_reset.index), "content_hash"].tolist():
                                conn.execute(
                                    text("""
                                        INSERT INTO budgetlens.income_source_excluded_hashes
                                            (source_id, content_hash)
                                        VALUES (:sid, :h) ON CONFLICT DO NOTHING
                                    """),
                                    {"sid": src_id, "h": h},
                                )
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with sc2:
            if st.button("🗑️ Delete", key=f"src_del_{src_id}"):
                try:
                    with get_engine().begin() as conn:
                        conn.execute(
                            text("DELETE FROM budgetlens.income_transaction_sources WHERE id = :id"),
                            {"id": src_id},
                        )
                    st.success(f"Deleted: {src['alias']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    return monthly


# ── Income sources grouped by entity ──────────────────────────────────────────

total_monthly_sources = 0.0

st.subheader("Income Sources")

if sources_df.empty:
    st.info("No income sources configured yet. Add one below.")
else:
    sources_df["_eid"] = sources_df["entity_id"].apply(
        lambda x: str(x) if x and not pd.isna(x) else None
    )
    unlinked = sources_df[sources_df["_eid"].isna()]

    tab_entities = [
        e for _, e in entities.iterrows()
        if not sources_df[sources_df["_eid"] == str(e["id"])].empty
    ]
    tab_names = [
        f"{'🏷️ ' if e['is_default'] else ''}{e['name']}"
        for e in tab_entities
    ]
    if not unlinked.empty:
        tab_names.append("Uncategorized")

    if tab_names:
        tabs = st.tabs(tab_names)
        for tab, e in zip(tabs[:len(tab_entities)], tab_entities):
            with tab:
                group = sources_df[sources_df["_eid"] == str(e["id"])]
                for _, src in group.iterrows():
                    total_monthly_sources += render_txn_source(src)
        if not unlinked.empty:
            with tabs[-1]:
                for _, src in unlinked.iterrows():
                    total_monthly_sources += render_txn_source(src)
    else:
        for _, src in sources_df.iterrows():
            total_monthly_sources += render_txn_source(src)

st.markdown("---")

# ── Add Income Source ──────────────────────────────────────────────────────────

st.subheader("Add Income Source")

if "add_src_gen" not in st.session_state:
    st.session_state["add_src_gen"] = 0
_gen = st.session_state["add_src_gen"]

a1, a2, a3 = st.columns(3)
with a1:
    add_alias = st.text_input(
        "Alias *", placeholder="e.g. Employer Payroll", key=f"add_alias_{_gen}"
    )
    add_entity = st.selectbox(
        "Entity",
        entity_options,
        index=entity_options.index(default_entity_id) if default_entity_id in entity_options else 0,
        format_func=lambda eid: entity_labels.get(eid, "— No entity —"),
        key=f"add_src_entity_{_gen}",
    )
with a2:
    add_filter_type = st.selectbox(
        "Filter type",
        list(FILTER_TYPES.keys()),
        format_func=lambda t: FILTER_TYPES[t],
        key=f"add_ftype_{_gen}",
    )
    add_filter_value = st.text_input(
        "Filter value *", placeholder="e.g. ACME CORP", key=f"add_fval_{_gen}"
    )
with a3:
    add_cadence = st.selectbox(
        "Cadence",
        list(CADENCE_OPTIONS.keys()),
        index=list(CADENCE_OPTIONS.keys()).index(default_cadence),
        format_func=lambda c: CADENCE_OPTIONS[c]["label"],
        key=f"add_cad_{_gen}",
    )

add_preview_df = None
add_preview = pd.DataFrame()
if add_filter_value and not txns_all.empty:
    add_preview = apply_filter(txns_all, add_filter_type, add_filter_value)
    if not add_preview.empty:
        add_preview_reset = add_preview.reset_index(drop=True)
        txn_add_display = add_preview_reset[["transaction_date", "description", "amount"]].copy()
        txn_add_display["transaction_date"] = txn_add_display["transaction_date"].astype(str)
        txn_add_display["amount"] = txn_add_display["amount"].astype(float)
        txn_add_display["Include"] = True
        txn_add_display = txn_add_display.rename(columns={
            "transaction_date": "Date",
            "description": "Description",
            "amount": "Amount ($)",
        })

        st.markdown("**Matching Transactions** — uncheck to exclude from the average")
        add_preview_df = st.data_editor(
            txn_add_display,
            column_config={
                "Date": st.column_config.TextColumn(disabled=True, width="small"),
                "Description": st.column_config.TextColumn(disabled=True, width="large"),
                "Amount ($)": st.column_config.NumberColumn(disabled=True, format="$%.2f", width="small"),
                "Include": st.column_config.CheckboxColumn(width="small"),
            },
            hide_index=True,
            use_container_width=True,
            key=f"add_preview_editor_{_gen}",
        )

        inc_mask = add_preview_df["Include"].values
        if inc_mask.any():
            avg = float(add_preview_reset.loc[inc_mask, "amount"].mean())
            monthly = monthly_from_cadence(avg, add_cadence)
            st.info(
                f"{int(inc_mask.sum())} selected  ·  avg ${avg:,.2f}  ·  "
                f"→ **${monthly:,.2f}/month**"
            )
        else:
            st.warning("No transactions selected.")
    else:
        st.warning("No transactions match this filter.")

btn1, btn2 = st.columns([1, 5])
with btn1:
    if st.button("➕ Add Source", type="primary", key="add_src_submit"):
        if not add_alias or not add_filter_value:
            st.error("Alias and filter value are required.")
        elif add_preview_df is None or not add_preview_df["Include"].any():
            st.error("Select at least one transaction to establish the average.")
        else:
            try:
                add_preview_reset = add_preview.reset_index(drop=True)
                inc_mask = add_preview_df["Include"].values

                with get_engine().begin() as conn:
                    result = conn.execute(
                        text("""
                            INSERT INTO budgetlens.income_transaction_sources
                                (alias, filter_type, filter_value, cadence, entity_id)
                            VALUES (:alias, :ftype, :fval, :cad, :eid)
                            RETURNING id
                        """),
                        {"alias": add_alias, "ftype": add_filter_type,
                         "fval": add_filter_value, "cad": add_cadence,
                         "eid": add_entity},
                    )
                    new_src_id = str(result.fetchone()[0])

                    for h in add_preview_reset.loc[~inc_mask, "content_hash"].tolist():
                        conn.execute(
                            text("""
                                INSERT INTO budgetlens.income_source_excluded_hashes
                                    (source_id, content_hash)
                                VALUES (:sid, :h) ON CONFLICT DO NOTHING
                            """),
                            {"sid": new_src_id, "h": h},
                        )

                avg = float(add_preview_reset.loc[inc_mask, "amount"].mean())
                monthly = monthly_from_cadence(avg, add_cadence)
                st.success(f"Income source **{add_alias}** added — ${monthly:,.2f}/month")
                st.session_state["add_src_gen"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add source: {e}")
with btn2:
    if st.button("🗑️ Clear", key="add_src_clear"):
        st.session_state["add_src_gen"] += 1
        st.rerun()

st.markdown("---")

# ── Custom Income Sources ─────────────────────────────────────────────────────

st.subheader("Custom Income Sources")
st.caption("Add income not captured in your bank transactions (freelance, rental, etc.).")

custom_monthly = 0.0

if not custom_sources_df.empty:
    for _, src in custom_sources_df.iterrows():
        src_monthly = monthly_from_cadence(float(src["amount"]), src["cadence"])
        if src["active"]:
            custom_monthly += src_monthly
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
            new_src_active = st.checkbox("Active", value=bool(src["active"]), key=f"sact_{src['id']}")
            new_src_monthly = monthly_from_cadence(new_src_amount, new_src_cad)
            st.info(f"Monthly equivalent: **${new_src_monthly:,.2f}/month**")

            dc1, dc2 = st.columns([1, 1])
            with dc1:
                if st.button("💾 Save", key=f"ssave_{src['id']}"):
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

if "add_custom_gen" not in st.session_state:
    st.session_state["add_custom_gen"] = 0
_cgen = st.session_state["add_custom_gen"]

ca1, ca2, ca3 = st.columns(3)
with ca1:
    custom_name = st.text_input("Name *", placeholder="e.g. Freelance", key=f"custom_name_{_cgen}")
with ca2:
    custom_amount = st.number_input(
        "Amount per paycheck ($) *", min_value=0.01, step=100.0, key=f"custom_amt_{_cgen}"
    )
with ca3:
    custom_cadence = st.selectbox(
        "Cadence",
        list(CADENCE_OPTIONS.keys()),
        index=1,
        format_func=lambda c: CADENCE_OPTIONS[c]["label"],
        key=f"custom_cad_{_cgen}",
    )

custom_add_monthly = monthly_from_cadence(custom_amount, custom_cadence)
st.info(f"Monthly equivalent: **${custom_add_monthly:,.2f}/month**")

cb1, cb2 = st.columns([1, 5])
with cb1:
    if st.button("➕ Add Custom Source", type="primary", key="add_custom_submit"):
        if not custom_name:
            st.error("Name is required.")
        else:
            try:
                with get_engine().begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO budgetlens.income_sources (name, amount, cadence)
                            VALUES (:name, :amt, :cad)
                        """),
                        {"name": custom_name, "amt": custom_amount, "cad": custom_cadence},
                    )
                st.success(f"Added **{custom_name}** — ${custom_add_monthly:,.2f}/month")
                st.session_state["add_custom_gen"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
with cb2:
    if st.button("🗑️ Clear", key="add_custom_clear"):
        st.session_state["add_custom_gen"] += 1
        st.rerun()

st.markdown("---")

# ── Monthly Income Summary ────────────────────────────────────────────────────

st.subheader("Monthly Income Summary")

total_monthly = total_monthly_sources + custom_monthly

c1, c2, c3 = st.columns(3)
c1.metric("From Income Sources", f"${total_monthly_sources:,.2f}/mo")
c2.metric("Custom Sources", f"${custom_monthly:,.2f}/mo")
c3.metric("Total Monthly Income", f"${total_monthly:,.2f}/mo")
