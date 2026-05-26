import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from src.db.connection import get_engine
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS
from src.bill_calculator import frequency_label, PERIOD_UNITS, monthly_equivalent

st.set_page_config(page_title="Entities — BudgetLens", layout="wide")
st.title("🏢 Entities")
st.caption("Entities group bills, expenses, and income — track finances for any person, household, or spending unit.")

CADENCE_LABELS = {"monthly": "Monthly", "semi_monthly": "Semi-Monthly", "biweekly": "Biweekly"}

# ── Load ───────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        entities = pd.read_sql(
            text("SELECT * FROM budgetlens.entities ORDER BY is_default DESC, name"),
            conn,
        )
        bills_df = pd.read_sql(
            text("""
                SELECT entity_id::text, name, amount, frequency, frequency_count,
                       monthly_equivalent, active
                FROM budgetlens.bills
                WHERE entity_id IS NOT NULL
                ORDER BY name
            """),
            conn,
        )
        txn_sources_df = pd.read_sql(
            text("""
                SELECT entity_id::text, alias, cadence, active
                FROM budgetlens.income_transaction_sources
                WHERE entity_id IS NOT NULL
                ORDER BY alias
            """),
            conn,
        )
        custom_sources_df = pd.read_sql(
            text("""
                SELECT entity_id::text, name, amount, cadence, active
                FROM budgetlens.income_sources
                WHERE entity_id IS NOT NULL
                ORDER BY name
            """),
            conn,
        )
        expenses_df = pd.read_sql(
            text("""
                SELECT * FROM budgetlens.entity_expenses
                ORDER BY entity_id, is_recurring DESC, name
            """),
            conn,
        )
        linked_txns_df = pd.read_sql(
            text("""
                SELECT etl.id::text AS link_id, etl.entity_id::text,
                       t.id::text AS transaction_id,
                       etl.notes, t.transaction_date, t.description, t.amount, t.category
                FROM budgetlens.entity_transaction_links etl
                JOIN budgetlens.transactions_deduped t ON t.id = etl.transaction_id
                ORDER BY t.transaction_date DESC
            """),
            conn,
        )
        all_txns_df = pd.read_sql(
            text("""
                SELECT id::text, transaction_date, description, amount, category
                FROM budgetlens.transactions_deduped
                ORDER BY transaction_date DESC
                LIMIT 2000
            """),
            conn,
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# ── Group data by entity ───────────────────────────────────────────────────────

bills_by_entity: dict = {}
if not bills_df.empty:
    for eid, grp in bills_df.groupby("entity_id"):
        bills_by_entity[eid] = grp.reset_index(drop=True)

income_by_entity: dict = {}
for df, kind in [(txn_sources_df, "txn"), (custom_sources_df, "custom")]:
    if df.empty:
        continue
    for eid, grp in df.groupby("entity_id"):
        if eid not in income_by_entity:
            income_by_entity[eid] = []
        for _, row in grp.iterrows():
            income_by_entity[eid].append({
                "name": row["alias"] if kind == "txn" else row["name"],
                "cadence": CADENCE_LABELS.get(row["cadence"], row["cadence"]),
                "active": row["active"],
            })

expenses_by_entity: dict = {}
if not expenses_df.empty:
    expenses_df["entity_id"] = expenses_df["entity_id"].astype(str)
    for eid, grp in expenses_df.groupby("entity_id"):
        expenses_by_entity[eid] = grp.reset_index(drop=True)

linked_by_entity: dict = {}
if not linked_txns_df.empty:
    for eid, grp in linked_txns_df.groupby("entity_id"):
        linked_by_entity[eid] = grp.reset_index(drop=True)


# ── Render: Expenses tab ───────────────────────────────────────────────────────

def render_expenses_tab(eid: str, expenses: pd.DataFrame):
    recurring = expenses[expenses["is_recurring"] == True] if not expenses.empty else pd.DataFrame()
    one_time = expenses[expenses["is_recurring"] == False] if not expenses.empty else pd.DataFrame()

    st.markdown("**Recurring Expenses**")
    if recurring.empty:
        st.caption("No recurring expenses yet.")
    else:
        for _, ex in recurring.iterrows():
            ex_id = str(ex["id"])
            freq = ex.get("frequency") or "months"
            cnt = int(ex.get("frequency_count") or 1)
            me = monthly_equivalent(float(ex["amount"]), freq, cnt)
            active_tag = "" if ex["active"] else " *(inactive)*"

            with st.expander(
                f"↺ **{ex['name']}**{active_tag} — "
                f"${float(ex['amount']):,.2f} {frequency_label(freq, cnt)} → **${me:,.2f}/mo**",
                expanded=False,
            ):
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_name = st.text_input("Name", value=ex["name"], key=f"ex_name_{ex_id}")
                    new_active = st.checkbox("Active", value=bool(ex["active"]), key=f"ex_active_{ex_id}")
                with c2:
                    new_amount = st.number_input(
                        "Amount ($)", value=float(ex["amount"]), min_value=0.01, key=f"ex_amt_{ex_id}"
                    )
                    new_cat = st.selectbox(
                        "Category",
                        ALL_CATEGORIES,
                        index=ALL_CATEGORIES.index(ex["category"]) if ex["category"] in ALL_CATEGORIES else 0,
                        format_func=lambda c: CATEGORY_LABELS.get(c, c),
                        key=f"ex_cat_{ex_id}",
                    )
                with c3:
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        new_cnt = st.number_input(
                            "Every", value=cnt, min_value=1, step=1, key=f"ex_cnt_{ex_id}"
                        )
                    with rc2:
                        new_freq = st.selectbox(
                            "Period",
                            list(PERIOD_UNITS.keys()),
                            index=list(PERIOD_UNITS.keys()).index(freq) if freq in PERIOD_UNITS else 1,
                            format_func=lambda u: PERIOD_UNITS[u],
                            key=f"ex_freq_{ex_id}",
                        )
                    sd_val = ex["start_date"]
                    if hasattr(sd_val, "date"):
                        sd_val = sd_val.date()
                    new_start = st.date_input(
                        "Start date",
                        value=sd_val if sd_val else date.today(),
                        key=f"ex_start_{ex_id}",
                    )
                    new_notes = st.text_input(
                        "Notes", value=ex.get("notes") or "", key=f"ex_notes_{ex_id}"
                    )

                new_me = monthly_equivalent(new_amount, new_freq, new_cnt)
                st.info(f"Monthly equivalent: **${new_me:,.2f}/month**")

                s1, s2 = st.columns([1, 1])
                with s1:
                    if st.button("💾 Save", key=f"ex_save_{ex_id}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("""
                                        UPDATE budgetlens.entity_expenses
                                        SET name=:name, amount=:amt, frequency=:freq,
                                            frequency_count=:cnt, start_date=:sd,
                                            category=:cat, notes=:notes, active=:active
                                        WHERE id=:id
                                    """),
                                    {"name": new_name, "amt": new_amount, "freq": new_freq,
                                     "cnt": new_cnt, "sd": new_start, "cat": new_cat,
                                     "notes": new_notes or None, "active": new_active, "id": ex_id},
                                )
                            st.success("Saved.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Save failed: {err}")
                with s2:
                    if st.button("🗑️ Delete", key=f"ex_del_{ex_id}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("DELETE FROM budgetlens.entity_expenses WHERE id=:id"),
                                    {"id": ex_id},
                                )
                            st.success("Deleted.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Delete failed: {err}")

    st.markdown("---")
    st.markdown("**One-Time Expenses**")
    if one_time.empty:
        st.caption("No one-time expenses yet.")
    else:
        for _, ex in one_time.iterrows():
            ex_id = str(ex["id"])
            exp_date = ex.get("expense_date")
            if hasattr(exp_date, "date"):
                exp_date = exp_date.date()
            exp_date = exp_date or date.today()

            with st.expander(
                f"◆ **{ex['name']}** — ${float(ex['amount']):,.2f} on {exp_date}",
                expanded=False,
            ):
                c1, c2 = st.columns(2)
                with c1:
                    new_name = st.text_input("Name", value=ex["name"], key=f"ex_name_{ex_id}")
                    new_amount = st.number_input(
                        "Amount ($)", value=float(ex["amount"]), min_value=0.01, key=f"ex_amt_{ex_id}"
                    )
                with c2:
                    new_date = st.date_input("Date", value=exp_date, key=f"ex_date_{ex_id}")
                    new_cat = st.selectbox(
                        "Category",
                        ALL_CATEGORIES,
                        index=ALL_CATEGORIES.index(ex["category"]) if ex["category"] in ALL_CATEGORIES else 0,
                        format_func=lambda c: CATEGORY_LABELS.get(c, c),
                        key=f"ex_cat_{ex_id}",
                    )
                new_notes = st.text_input(
                    "Notes", value=ex.get("notes") or "", key=f"ex_notes_{ex_id}"
                )

                s1, s2 = st.columns([1, 1])
                with s1:
                    if st.button("💾 Save", key=f"ex_save_{ex_id}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("""
                                        UPDATE budgetlens.entity_expenses
                                        SET name=:name, amount=:amt, expense_date=:edate,
                                            category=:cat, notes=:notes
                                        WHERE id=:id
                                    """),
                                    {"name": new_name, "amt": new_amount, "edate": new_date,
                                     "cat": new_cat, "notes": new_notes or None, "id": ex_id},
                                )
                            st.success("Saved.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Save failed: {err}")
                with s2:
                    if st.button("🗑️ Delete", key=f"ex_del_{ex_id}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("DELETE FROM budgetlens.entity_expenses WHERE id=:id"),
                                    {"id": ex_id},
                                )
                            st.success("Deleted.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Delete failed: {err}")

    st.markdown("---")
    st.markdown("**Add Expense**")

    if f"add_ex_gen_{eid}" not in st.session_state:
        st.session_state[f"add_ex_gen_{eid}"] = 0
    gen = st.session_state[f"add_ex_gen_{eid}"]

    is_recurring = st.checkbox("Recurring", value=True, key=f"add_ex_recur_{eid}_{gen}")

    fa1, fa2, fa3 = st.columns(3)
    with fa1:
        add_name = st.text_input(
            "Name *", placeholder="e.g. Storage unit", key=f"add_ex_name_{eid}_{gen}"
        )
        add_amount = st.number_input(
            "Amount ($)", min_value=0.01, step=10.0, key=f"add_ex_amt_{eid}_{gen}"
        )
    with fa2:
        add_cat = st.selectbox(
            "Category",
            ALL_CATEGORIES,
            format_func=lambda c: CATEGORY_LABELS.get(c, c),
            key=f"add_ex_cat_{eid}_{gen}",
        )
        add_notes = st.text_input("Notes", key=f"add_ex_notes_{eid}_{gen}")
    with fa3:
        if is_recurring:
            rc1, rc2 = st.columns(2)
            with rc1:
                add_cnt = st.number_input(
                    "Every", value=1, min_value=1, step=1, key=f"add_ex_cnt_{eid}_{gen}"
                )
            with rc2:
                add_freq = st.selectbox(
                    "Period",
                    list(PERIOD_UNITS.keys()),
                    index=1,
                    format_func=lambda u: PERIOD_UNITS[u],
                    key=f"add_ex_freq_{eid}_{gen}",
                )
            add_start = st.date_input(
                "Start date", value=date.today(), key=f"add_ex_start_{eid}_{gen}"
            )
            add_exp_date = date.today()
            add_me = monthly_equivalent(add_amount if add_amount else 0.0, add_freq, add_cnt)
            st.info(f"Monthly equivalent: **${add_me:,.2f}/month**")
        else:
            add_cnt = 1
            add_freq = "months"
            add_start = date.today()
            add_exp_date = st.date_input(
                "Expense date", value=date.today(), key=f"add_ex_date_{eid}_{gen}"
            )

    ab1, ab2 = st.columns([1, 5])
    with ab1:
        if st.button("➕ Add", type="primary", key=f"add_ex_submit_{eid}"):
            if not add_name:
                st.error("Name is required.")
            else:
                try:
                    with get_engine().begin() as conn:
                        if is_recurring:
                            conn.execute(
                                text("""
                                    INSERT INTO budgetlens.entity_expenses
                                        (entity_id, name, amount, is_recurring, frequency,
                                         frequency_count, start_date, category, notes)
                                    VALUES
                                        (:eid, :name, :amt, TRUE, :freq, :cnt, :sd, :cat, :notes)
                                """),
                                {"eid": eid, "name": add_name, "amt": add_amount,
                                 "freq": add_freq, "cnt": add_cnt, "sd": add_start,
                                 "cat": add_cat, "notes": add_notes or None},
                            )
                        else:
                            conn.execute(
                                text("""
                                    INSERT INTO budgetlens.entity_expenses
                                        (entity_id, name, amount, is_recurring,
                                         expense_date, category, notes)
                                    VALUES
                                        (:eid, :name, :amt, FALSE, :edate, :cat, :notes)
                                """),
                                {"eid": eid, "name": add_name, "amt": add_amount,
                                 "edate": add_exp_date, "cat": add_cat, "notes": add_notes or None},
                            )
                    st.success(f"Added **{add_name}**.")
                    st.session_state[f"add_ex_gen_{eid}"] += 1
                    st.rerun()
                except Exception as err:
                    st.error(f"Failed: {err}")
    with ab2:
        if st.button("🗑️ Clear", key=f"add_ex_clear_{eid}"):
            st.session_state[f"add_ex_gen_{eid}"] += 1
            st.rerun()


# ── Render: Linked Transactions tab ───────────────────────────────────────────

def render_linked_txns_tab(eid: str, linked: pd.DataFrame, all_txns: pd.DataFrame):
    st.markdown("**Linked Transactions**")
    if linked.empty:
        st.caption("No transactions linked yet.")
    else:
        for _, lnk in linked.iterrows():
            c1, c2 = st.columns([6, 1])
            with c1:
                cat_label = CATEGORY_LABELS.get(lnk["category"], lnk["category"])
                note_str = f" · *{lnk['notes']}*" if lnk.get("notes") else ""
                st.markdown(
                    f"**{lnk['transaction_date']}** | {lnk['description']} | "
                    f"${abs(float(lnk['amount'])):,.2f} | {cat_label}{note_str}"
                )
            with c2:
                if st.button("Unlink", key=f"unlink_{lnk['link_id']}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("DELETE FROM budgetlens.entity_transaction_links WHERE id=:id"),
                                {"id": lnk["link_id"]},
                            )
                        st.rerun()
                    except Exception as err:
                        st.error(f"Failed: {err}")

    st.markdown("---")
    st.markdown("**Link a Transaction**")

    linked_ids = set(linked["transaction_id"].tolist()) if not linked.empty else set()
    available = all_txns[~all_txns["id"].isin(linked_ids)].copy()

    search_q = st.text_input(
        "Search", placeholder="e.g. Walmart", key=f"link_search_{eid}"
    )
    if search_q:
        available = available[
            available["description"].str.contains(search_q, case=False, na=False)
        ]

    if available.empty:
        st.caption("No transactions available to link.")
        return

    available = available.head(50)
    available["label"] = (
        available["transaction_date"].astype(str) + " | "
        + available["description"] + " | $"
        + available["amount"].abs().map("{:.2f}".format)
    )

    selected_label = st.selectbox(
        "Select transaction",
        ["— Select —"] + available["label"].tolist(),
        key=f"link_sel_{eid}",
    )
    link_notes = st.text_input("Notes (optional)", key=f"link_notes_{eid}")

    if st.button("🔗 Link", key=f"link_btn_{eid}"):
        if selected_label == "— Select —":
            st.warning("Select a transaction first.")
        else:
            idx = available["label"].tolist().index(selected_label)
            txn_id = available.iloc[idx]["id"]
            try:
                with get_engine().begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO budgetlens.entity_transaction_links
                                (entity_id, transaction_id, notes)
                            VALUES (:eid, :tid, :notes)
                            ON CONFLICT DO NOTHING
                        """),
                        {"eid": eid, "tid": txn_id, "notes": link_notes or None},
                    )
                st.success("Transaction linked.")
                st.rerun()
            except Exception as err:
                st.error(f"Failed: {err}")


# ── Entity cards ──────────────────────────────────────────────────────────────

if entities.empty:
    st.info("No entities yet. Create one below.")
else:
    for _, e in entities.iterrows():
        eid = str(e["id"])
        default_badge = " 🏷️ *default*" if e["is_default"] else ""
        bills_n = len(bills_by_entity.get(eid, pd.DataFrame()))
        income_n = len(income_by_entity.get(eid, []))
        expense_n = len(expenses_by_entity.get(eid, pd.DataFrame()))
        linked_n = len(linked_by_entity.get(eid, pd.DataFrame()))

        with st.expander(
            f"**{e['name']}**{default_badge}  —  "
            f"{bills_n} bill(s) · {income_n} income source(s) · "
            f"{expense_n} expense(s) · {linked_n} linked transaction(s)",
            expanded=False,
        ):
            if e["description"]:
                st.caption(e["description"])

            entity_bills = bills_by_entity.get(eid, pd.DataFrame())
            entity_income = income_by_entity.get(eid, [])

            if not entity_bills.empty or entity_income:
                left, right = st.columns(2)
                with left:
                    st.markdown("**Bills**")
                    if entity_bills.empty:
                        st.caption("No bills linked.")
                    else:
                        for _, b in entity_bills.iterrows():
                            active_tag = "" if b["active"] else " *(inactive)*"
                            freq = frequency_label(b["frequency"], int(b["frequency_count"] or 1))
                            st.markdown(
                                f"- {b['name']}{active_tag} — "
                                f"${float(b['amount']):,.2f} {freq} "
                                f"*(${float(b['monthly_equivalent']):,.2f}/mo)*"
                            )
                with right:
                    st.markdown("**Income Sources**")
                    if not entity_income:
                        st.caption("No income sources linked.")
                    else:
                        for src in entity_income:
                            active_tag = "" if src["active"] else " *(inactive)*"
                            st.markdown(f"- {src['name']}{active_tag} — {src['cadence']}")

                st.markdown("---")

            exp_tab, txn_tab, settings_tab = st.tabs(
                ["Expenses", "Linked Transactions", "Entity Settings"]
            )

            with exp_tab:
                render_expenses_tab(eid, expenses_by_entity.get(eid, pd.DataFrame()))

            with txn_tab:
                render_linked_txns_tab(
                    eid, linked_by_entity.get(eid, pd.DataFrame()), all_txns_df
                )

            with settings_tab:
                e1, e2 = st.columns(2)
                with e1:
                    new_name = st.text_input("Name", value=e["name"], key=f"ename_{eid}")
                with e2:
                    new_desc = st.text_area(
                        "Description", value=e["description"] or "",
                        key=f"edesc_{eid}", height=68,
                    )

                sc1, sc2, sc3 = st.columns([1, 1, 2])
                with sc1:
                    if st.button("💾 Save", key=f"esave_{eid}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("""
                                        UPDATE budgetlens.entities
                                        SET name=:name, description=:desc WHERE id=:id
                                    """),
                                    {"name": new_name, "desc": new_desc or None, "id": eid},
                                )
                            st.success("Saved.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Save failed: {err}")
                with sc2:
                    if not e["is_default"]:
                        if st.button("Set as Default", key=f"edefault_{eid}"):
                            try:
                                with get_engine().begin() as conn:
                                    conn.execute(
                                        text("UPDATE budgetlens.entities SET is_default = FALSE")
                                    )
                                    conn.execute(
                                        text("UPDATE budgetlens.entities SET is_default = TRUE WHERE id=:id"),
                                        {"id": eid},
                                    )
                                st.success(f"**{e['name']}** is now the default entity.")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Failed: {err}")
                with sc3:
                    if st.button("🗑️ Delete Entity", key=f"edel_{eid}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(
                                    text("DELETE FROM budgetlens.entities WHERE id=:id"),
                                    {"id": eid},
                                )
                            st.success(f"Deleted **{e['name']}**.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Delete failed: {err}")

st.markdown("---")

# ── Add Entity ────────────────────────────────────────────────────────────────

st.subheader("Add Entity")

if "entity_form_gen" not in st.session_state:
    st.session_state["entity_form_gen"] = 0
_gen = st.session_state["entity_form_gen"]

p1, p2 = st.columns(2)
with p1:
    new_entity_name = st.text_input(
        "Name *",
        placeholder="e.g. Joint, Personal, Rental Property",
        key=f"ef_name_{_gen}",
    )
with p2:
    new_entity_desc = st.text_area(
        "Description", placeholder="Optional notes", key=f"ef_desc_{_gen}", height=68
    )

make_default = st.checkbox("Set as default", value=entities.empty, key=f"ef_default_{_gen}")

b1, b2 = st.columns([1, 5])
with b1:
    if st.button("➕ Add Entity", type="primary", key="add_entity_submit"):
        if not new_entity_name:
            st.error("Name is required.")
        else:
            try:
                with get_engine().begin() as conn:
                    if make_default:
                        conn.execute(text("UPDATE budgetlens.entities SET is_default = FALSE"))
                    conn.execute(
                        text("""
                            INSERT INTO budgetlens.entities (name, description, is_default)
                            VALUES (:name, :desc, :def)
                        """),
                        {"name": new_entity_name, "desc": new_entity_desc or None, "def": make_default},
                    )
                st.success(f"Entity **{new_entity_name}** created.")
                st.session_state["entity_form_gen"] += 1
                st.rerun()
            except Exception as err:
                st.error(f"Failed: {err}")
with b2:
    if st.button("🗑️ Clear", key="clear_entity_form"):
        st.session_state["entity_form_gen"] += 1
        st.rerun()
