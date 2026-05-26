import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS
from src.bill_calculator import (
    PERIOD_UNITS, next_charge_date,
    bill_status, hit_months, frequency_label,
)

st.set_page_config(page_title="Bills — BudgetLens", layout="wide")
st.title("🧾 Bills Manager")

FILTER_TYPES = {
    "contains":    "Contains",
    "starts_with": "Starts With",
    "regex":       "Regex",
}

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


def _count_periods(dates: pd.Series, unit: str, count: int) -> int:
    """Count distinct billing cycles by bucketing dates into freq-sized windows."""
    dt = pd.to_datetime(dates)
    if unit == "years":
        buckets = set((dt.dt.year // count).tolist())
    elif unit == "weeks":
        epoch = pd.Timestamp("2000-01-03")
        week_nums = ((dt - epoch) / pd.Timedelta(weeks=1)).astype(int)
        buckets = set((week_nums // count).tolist())
    else:  # months
        month_nums = dt.dt.year * 12 + dt.dt.month
        buckets = set((month_nums // count).tolist())
    return max(len(buckets), 1)


_MONTHS_PER_UNIT = {"months": 1, "years": 12, "weeks": 12 / 52}


def compute_monthly(amounts: pd.Series, dates: pd.Series, unit: str, count: int) -> float:
    """Sum selected amounts divided by (distinct billing cycles × months per cycle)."""
    if amounts.empty:
        return 0.0
    n_periods = _count_periods(dates, unit, count)
    months = n_periods * count * _MONTHS_PER_UNIT.get(unit, 1)
    return float(amounts.abs().sum()) / months


# ── Load ───────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        bills = pd.read_sql(
            text("SELECT * FROM budgetlens.bills ORDER BY active DESC, name"),
            conn,
        )
        entities = pd.read_sql(
            text("SELECT id, name, is_default FROM budgetlens.entities ORDER BY is_default DESC, name"),
            conn,
        )
        txns_all = pd.read_sql(
            text("""
                SELECT txn_hash, content_hash, description, transaction_date, amount
                FROM budgetlens.transactions_deduped
                WHERE amount < 0
                ORDER BY transaction_date DESC
            """),
            conn,
        )
        excluded_df = pd.read_sql(
            text("SELECT bill_id::text, content_hash FROM budgetlens.bill_excluded_hashes"),
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

excluded_by_bill: dict[str, set[str]] = {}
if not excluded_df.empty:
    for bid, grp in excluded_df.groupby("bill_id"):
        excluded_by_bill[bid] = set(grp["content_hash"].tolist())

# ── Totals ─────────────────────────────────────────────────────────────────────

active_bills = bills[bills["active"] == True] if not bills.empty else pd.DataFrame()
total_monthly = float(active_bills["monthly_equivalent"].sum()) if not active_bills.empty else 0.0

st.metric("Total Committed Monthly Spend", f"${total_monthly:,.2f}")
st.caption("Sum of all active bills converted to monthly equivalents")
st.markdown("---")

# ── Bill card renderer ─────────────────────────────────────────────────────────

STATUS_EMOJI = {"paid": "🟢", "due_soon": "🟡", "overdue": "🔴", "upcoming": "⚪"}

today = date.today()
from_month = date(today.year, today.month, 1)


def render_bill_card(b):
    bill_id = str(b["id"])
    filter_type = b.get("filter_type") or "contains"
    filter_value = b.get("filter_value") or ""

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

    freq_unit = b["frequency"]
    freq_count = int(b.get("frequency_count", 1) or 1)
    status = bill_status(nxt, last, freq_unit, freq_count)
    emoji = STATUS_EMOJI[status]
    active_label = "" if b["active"] else " *(inactive)*"
    freq_display = frequency_label(freq_unit, freq_count)

    matched = apply_filter(txns_all, filter_type, filter_value) if filter_value else pd.DataFrame()

    with st.expander(
        f"{emoji} **{b['name']}**{active_label}  —  ${float(b['monthly_equivalent']):,.2f}/month",
        expanded=False,
    ):
        txn_edited = None
        include_mask = []
        live_monthly = float(b["monthly_equivalent"])
        matched_reset = pd.DataFrame()

        if filter_value:
            st.markdown("**Matched Transactions** — uncheck to exclude from the average")
            if matched.empty:
                st.caption("No transactions match this filter.")
            else:
                excluded_hashes = excluded_by_bill.get(bill_id, set())
                matched_reset = matched.reset_index(drop=True)
                included_mask_stored = ~matched_reset["content_hash"].isin(excluded_hashes)

                # Stable base: keep Include state in session_state so the
                # data_editor delta is always applied to the same base, preventing
                # "all rows re-select" when the base changes between reruns.
                base_key = f"include_base_{bill_id}"
                override_key = f"include_override_{bill_id}"
                override = st.session_state.pop(override_key, None)

                if override is not None:
                    st.session_state[base_key] = [override] * len(matched_reset)
                    st.session_state.pop(f"txn_editor_{bill_id}", None)
                elif base_key not in st.session_state:
                    st.session_state[base_key] = included_mask_stored.values.tolist()

                _sa, _da, _ = st.columns([1, 1, 8])
                with _sa:
                    if st.button("Select All", key=f"sel_all_{bill_id}", use_container_width=True):
                        st.session_state[override_key] = True
                        st.rerun()
                with _da:
                    if st.button("Deselect All", key=f"desel_all_{bill_id}", use_container_width=True):
                        st.session_state[override_key] = False
                        st.rerun()

                txn_display = matched_reset[["transaction_date", "description", "amount"]].copy()
                txn_display["transaction_date"] = txn_display["transaction_date"].astype(str)
                txn_display["amount"] = txn_display["amount"].abs().astype(float)
                txn_display["Include"] = st.session_state[base_key]
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
                    key=f"txn_editor_{bill_id}",
                )
                include_mask = txn_edited["Include"].values
                if include_mask.any():
                    sel_amounts = matched_reset.loc[include_mask, "amount"]
                    sel_dates = matched_reset.loc[include_mask, "transaction_date"]
                    live_monthly = compute_monthly(sel_amounts, sel_dates, freq_unit, freq_count)
                    n_periods = _count_periods(sel_dates, freq_unit, freq_count)
                    period_label = freq_unit.rstrip("s")  # "months"→"month", "years"→"year", "weeks"→"week"
                    st.caption(
                        f"{int(include_mask.sum())} transactions  ·  "
                        f"{n_periods} {period_label}(s)  ·  "
                        f"total ${float(sel_amounts.abs().sum()):,.2f}  ·  "
                        f"→ **${live_monthly:,.2f}/month**"
                    )
                else:
                    live_monthly = 0.0

        st.markdown("---")
        st.markdown("**Bill Settings**")

        e1, e2, e3 = st.columns(3)
        with e1:
            new_name = st.text_input("Name", value=b["name"], key=f"bname_{bill_id}")
            new_active = st.checkbox("Active", value=bool(b["active"]), key=f"bactive_{bill_id}")
            cur_entity = str(b["entity_id"]) if b.get("entity_id") and not pd.isna(b.get("entity_id")) else None
            new_entity = st.selectbox(
                "Entity",
                entity_options,
                index=entity_options.index(cur_entity) if cur_entity in entity_options else 0,
                format_func=lambda eid: entity_labels.get(eid, "— No entity —"),
                key=f"bentity_{bill_id}",
            )
        with e2:
            new_filter_type = st.selectbox(
                "Filter type",
                list(FILTER_TYPES.keys()),
                index=list(FILTER_TYPES.keys()).index(filter_type) if filter_type in FILTER_TYPES else 0,
                format_func=lambda t: FILTER_TYPES[t],
                key=f"bftype_{bill_id}",
            )
            new_filter_value = st.text_input(
                "Filter value", value=filter_value, key=f"bfval_{bill_id}"
            )
            new_cat = st.selectbox(
                "Category",
                ALL_CATEGORIES,
                index=ALL_CATEGORIES.index(b["category"]) if b["category"] in ALL_CATEGORIES else 0,
                format_func=lambda c: CATEGORY_LABELS.get(c, c),
                key=f"bcat_{bill_id}",
            )
        with e3:
            bc1, bc2 = st.columns(2)
            with bc1:
                new_count = st.number_input(
                    "Every", value=freq_count, min_value=1, step=1, key=f"bcnt_{bill_id}"
                )
            with bc2:
                new_unit = st.selectbox(
                    "Period",
                    list(PERIOD_UNITS.keys()),
                    index=list(PERIOD_UNITS.keys()).index(freq_unit) if freq_unit in PERIOD_UNITS else 1,
                    format_func=lambda u: PERIOD_UNITS[u],
                    key=f"bunit_{bill_id}",
                )
            use_override = st.checkbox(
                "Override amount", value=False, key=f"bovr_toggle_{bill_id}"
            )
            new_override = None
            if use_override:
                base = live_monthly if live_monthly > 0 else float(b["monthly_equivalent"])
                new_override = st.number_input(
                    "Monthly amount ($)", value=round(base, 2), min_value=0.01, key=f"bovr_{bill_id}"
                )

        has_txns = txn_edited is not None and include_mask.any()
        me_preview = (
            new_override if (use_override and new_override)
            else live_monthly if has_txns
            else float(b["monthly_equivalent"])
        )
        stored_amount = (
            float(matched_reset.loc[include_mask, "amount"].abs().mean())
            if has_txns else float(b["amount"])
        )
        st.info(f"Monthly equivalent: **${me_preview:,.2f}/month**")

        st.markdown("**Charge calendar (next 12 months):**")
        start_date = b["start_date"]
        if hasattr(start_date, "date"):
            start_date = start_date.date()
        hit = hit_months(start_date, new_unit, new_count, from_month, 12)
        month_cells = []
        for i in range(12):
            m = from_month.replace(
                month=(from_month.month - 1 + i) % 12 + 1,
                year=from_month.year + (from_month.month - 1 + i) // 12,
            )
            mkey = m.strftime("%Y-%m")
            month_cells.append(f"**:blue[{m.strftime('%b')}]**" if mkey in hit else m.strftime("%b"))
        st.markdown(" · ".join(month_cells))

        if b.get("notes"):
            st.caption(f"Notes: {b['notes']}")

        sc1, sc2 = st.columns([1, 1])
        with sc1:
            if st.button("💾 Save", type="primary", key=f"bsave_{bill_id}"):
                try:
                    new_last = last
                    if has_txns:
                        most_recent_raw = matched_reset.loc[include_mask, "transaction_date"].max()
                        new_last = most_recent_raw.date() if hasattr(most_recent_raw, "date") else most_recent_raw
                    new_ncd = next_charge_date(new_last, new_unit, new_count) if new_last else None

                    with get_engine().begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE budgetlens.bills
                                SET name = :name, category = :cat, frequency = :unit,
                                    frequency_count = :cnt, amount = :amt,
                                    monthly_equivalent = :me, active = :active,
                                    filter_type = :ftype, filter_value = :fval,
                                    entity_id = :eid,
                                    last_charge_date = :lcd, next_charge_date = :ncd
                                WHERE id = :id
                            """),
                            {"name": new_name, "cat": new_cat, "unit": new_unit,
                             "cnt": new_count, "amt": stored_amount, "me": me_preview,
                             "active": new_active, "ftype": new_filter_type,
                             "fval": new_filter_value or None,
                             "eid": new_entity, "lcd": new_last, "ncd": new_ncd,
                             "id": bill_id},
                        )
                        if txn_edited is not None and not matched_reset.empty:
                            group_hashes = matched_reset["content_hash"].tolist()
                            conn.execute(
                                text("""
                                    DELETE FROM budgetlens.bill_excluded_hashes
                                    WHERE bill_id = :bid AND content_hash = ANY(:hashes)
                                """),
                                {"bid": bill_id, "hashes": group_hashes},
                            )
                            for h in matched_reset.loc[~txn_edited["Include"].values, "content_hash"].tolist():
                                conn.execute(
                                    text("""
                                        INSERT INTO budgetlens.bill_excluded_hashes (bill_id, content_hash)
                                        VALUES (:bid, :h) ON CONFLICT DO NOTHING
                                    """),
                                    {"bid": bill_id, "h": h},
                                )
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with sc2:
            if st.button("🗑️ Delete", key=f"bdel_{bill_id}"):
                try:
                    with get_engine().begin() as conn:
                        conn.execute(
                            text("DELETE FROM budgetlens.bills WHERE id = :id"),
                            {"id": bill_id},
                        )
                    st.success(f"Deleted: {b['name']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")


# ── Bills grouped by entity ────────────────────────────────────────────────────

if bills.empty:
    st.info("No bills configured yet. Add one below.")
else:
    bills["_eid"] = bills["entity_id"].apply(
        lambda x: str(x) if x and not pd.isna(x) else None
    )
    unlinked = bills[bills["_eid"].isna()]

    tab_entities = [
        e for _, e in entities.iterrows()
        if not bills[bills["_eid"] == str(e["id"])].empty
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
                group = bills[bills["_eid"] == str(e["id"])]
                monthly_sum = float(group[group["active"] == True]["monthly_equivalent"].sum())
                st.caption(f"{len(group)} bill(s) · ${monthly_sum:,.2f}/month committed")
                for _, b in group.iterrows():
                    render_bill_card(b)
        if not unlinked.empty:
            with tabs[-1]:
                monthly_unlinked = float(unlinked[unlinked["active"] == True]["monthly_equivalent"].sum())
                st.caption(f"{len(unlinked)} bill(s) · ${monthly_unlinked:,.2f}/month committed")
                for _, b in unlinked.iterrows():
                    render_bill_card(b)
    else:
        for _, b in bills.iterrows():
            render_bill_card(b)

st.markdown("---")

# ── Add New Bill ───────────────────────────────────────────────────────────────

st.subheader("Add New Bill")

if "add_bill_gen" not in st.session_state:
    st.session_state["add_bill_gen"] = 0
_gen = st.session_state["add_bill_gen"]

a1, a2, a3 = st.columns(3)
with a1:
    add_name = st.text_input("Bill name *", placeholder="e.g. Mortgage", key=f"add_name_{_gen}")
    add_cat = st.selectbox(
        "Category",
        ALL_CATEGORIES,
        format_func=lambda c: CATEGORY_LABELS.get(c, c),
        key=f"add_cat_{_gen}",
    )
    add_entity = st.selectbox(
        "Entity",
        entity_options,
        index=entity_options.index(default_entity_id) if default_entity_id in entity_options else 0,
        format_func=lambda eid: entity_labels.get(eid, "— No entity —"),
        key=f"add_entity_{_gen}",
    )
with a2:
    add_filter_type = st.selectbox(
        "Filter type",
        list(FILTER_TYPES.keys()),
        format_func=lambda t: FILTER_TYPES[t],
        key=f"add_ftype_{_gen}",
    )
    add_filter_value = st.text_input(
        "Filter value *", placeholder="e.g. LAKEVIEW LN SRV", key=f"add_fval_{_gen}"
    )
with a3:
    fc1, fc2 = st.columns(2)
    with fc1:
        add_count = st.number_input("Every", value=1, min_value=1, step=1, key=f"add_count_{_gen}")
    with fc2:
        add_unit = st.selectbox(
            "Period",
            list(PERIOD_UNITS.keys()),
            index=1,
            format_func=lambda u: PERIOD_UNITS[u],
            key=f"add_unit_{_gen}",
        )
    add_notes = st.text_input("Notes (optional)", key=f"add_notes_{_gen}")

# Transaction preview
add_preview_df = None
add_preview = pd.DataFrame()
if add_filter_value and not txns_all.empty:
    add_preview = apply_filter(txns_all, add_filter_type, add_filter_value)
    if not add_preview.empty:
        add_preview_reset = add_preview.reset_index(drop=True)
        txn_add_display = add_preview_reset[["transaction_date", "description", "amount"]].copy()
        txn_add_display["transaction_date"] = txn_add_display["transaction_date"].astype(str)
        txn_add_display["amount"] = txn_add_display["amount"].abs().astype(float)
        txn_add_display["Include"] = True
        txn_add_display = txn_add_display.rename(columns={
            "transaction_date": "Date",
            "description": "Description",
            "amount": "Amount ($)",
        })

        st.markdown("**Matching Transactions** — uncheck to exclude from the average")

        _add_base_key = f"add_include_base_{_gen}"
        _add_override_key = "add_include_override"
        _add_override = st.session_state.pop(_add_override_key, None)

        if _add_override is not None:
            st.session_state[_add_base_key] = [_add_override] * len(txn_add_display)
            st.session_state.pop(f"add_preview_editor_{_gen}", None)
        elif _add_base_key not in st.session_state:
            st.session_state[_add_base_key] = [True] * len(txn_add_display)

        txn_add_display["Include"] = st.session_state[_add_base_key]

        _asa, _ada, _ = st.columns([1, 1, 8])
        with _asa:
            if st.button("Select All", key="add_sel_all", use_container_width=True):
                st.session_state[_add_override_key] = True
                st.rerun()
        with _ada:
            if st.button("Deselect All", key="add_desel_all", use_container_width=True):
                st.session_state[_add_override_key] = False
                st.rerun()

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
            sel_amounts = add_preview_reset.loc[inc_mask, "amount"]
            sel_dates = add_preview_reset.loc[inc_mask, "transaction_date"]
            monthly_add = compute_monthly(sel_amounts, sel_dates, add_unit, add_count)
            n_periods = _count_periods(sel_dates, add_unit, add_count)
            period_label = add_unit.rstrip("s")
            st.info(
                f"{int(inc_mask.sum())} transactions  ·  {n_periods} {period_label}(s)  ·  "
                f"total ${float(sel_amounts.abs().sum()):,.2f}  ·  "
                f"→ **${monthly_add:,.2f}/month**"
            )
        else:
            st.warning("No transactions selected.")
    else:
        st.warning("No transactions match this filter.")

btn1, btn2 = st.columns([1, 5])
with btn1:
    if st.button("➕ Add Bill", type="primary", key="add_bill_submit"):
        if not add_name or not add_filter_value:
            st.error("Bill name and filter value are required.")
        elif add_preview_df is None or not add_preview_df["Include"].any():
            st.error("Select at least one transaction to determine the bill amount.")
        else:
            try:
                add_preview_reset = add_preview.reset_index(drop=True)
                inc_mask = add_preview_df["Include"].values
                sel_amounts = add_preview_reset.loc[inc_mask, "amount"]
                sel_dates = add_preview_reset.loc[inc_mask, "transaction_date"]
                amount = float(sel_amounts.abs().mean())
                me = compute_monthly(sel_amounts, sel_dates, add_unit, add_count)

                dates = add_preview_reset.loc[inc_mask, "transaction_date"]
                last_dt = dates.max()
                first_dt = dates.min()
                if hasattr(last_dt, "date"):
                    last_dt = last_dt.date()
                if hasattr(first_dt, "date"):
                    first_dt = first_dt.date()
                ncd = next_charge_date(last_dt, add_unit, add_count)

                with get_engine().begin() as conn:
                    result = conn.execute(
                        text("""
                            INSERT INTO budgetlens.bills
                                (name, category, frequency, frequency_count, amount,
                                 monthly_equivalent, start_date, last_charge_date, next_charge_date,
                                 notes, filter_type, filter_value, entity_id)
                            VALUES
                                (:name, :cat, :unit, :cnt, :amt, :me, :sd, :lcd, :ncd,
                                 :notes, :ftype, :fval, :eid)
                            RETURNING id
                        """),
                        {"name": add_name, "cat": add_cat, "unit": add_unit, "cnt": add_count,
                         "amt": amount, "me": me, "sd": first_dt, "lcd": last_dt, "ncd": ncd,
                         "notes": add_notes or None, "ftype": add_filter_type,
                         "fval": add_filter_value, "eid": add_entity},
                    )
                    new_bill_id = str(result.fetchone()[0])

                    for h in add_preview_reset.loc[~inc_mask, "content_hash"].tolist():
                        conn.execute(
                            text("""
                                INSERT INTO budgetlens.bill_excluded_hashes (bill_id, content_hash)
                                VALUES (:bid, :h) ON CONFLICT DO NOTHING
                            """),
                            {"bid": new_bill_id, "h": h},
                        )

                    # Write bill_id + category into transaction_attributes (keyed by txn_hash)
                    for txn_hash in add_preview_reset["txn_hash"].tolist():
                        conn.execute(
                            text("""
                                INSERT INTO budgetlens.transaction_attributes
                                    (txn_hash, category, category_overridden, bill_id)
                                VALUES (:txn_hash, :cat, TRUE, :bid)
                                ON CONFLICT (txn_hash) DO UPDATE
                                    SET bill_id = EXCLUDED.bill_id,
                                        category = EXCLUDED.category,
                                        category_overridden = TRUE,
                                        updated_at = NOW()
                            """),
                            {"txn_hash": txn_hash, "cat": add_cat, "bid": new_bill_id},
                        )

                st.success(
                    f"Bill **{add_name}** added — ${me:,.2f}/month  ·  "
                    f"{len(add_preview_reset)} transaction(s) linked"
                )
                st.session_state["add_bill_gen"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add bill: {e}")
with btn2:
    if st.button("🗑️ Clear", key="add_bill_clear"):
        st.session_state["add_bill_gen"] += 1
        st.rerun()
