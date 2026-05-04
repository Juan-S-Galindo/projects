import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.db.connection import get_engine

st.set_page_config(page_title="Profiles — BudgetLens", layout="wide")
st.title("👤 Profiles")
st.caption("Profiles group bills and income sources together — useful for tracking multiple people or scenarios.")

# ── Load ───────────────────────────────────────────────────────────────────────

try:
    with get_engine().connect() as conn:
        profiles = pd.read_sql(
            text("SELECT * FROM budgetlens.profiles ORDER BY is_default DESC, name"),
            conn,
        )
        bills_df = pd.read_sql(
            text("""
                SELECT profile_id::text, name, amount, frequency, frequency_count,
                       monthly_equivalent, active
                FROM budgetlens.bills
                WHERE profile_id IS NOT NULL
                ORDER BY name
            """),
            conn,
        )
        txn_sources_df = pd.read_sql(
            text("""
                SELECT profile_id::text, alias, cadence, amount_override, active
                FROM budgetlens.income_transaction_sources
                WHERE profile_id IS NOT NULL
                ORDER BY alias
            """),
            conn,
        )
        custom_sources_df = pd.read_sql(
            text("""
                SELECT profile_id::text, name, amount, cadence, active
                FROM budgetlens.income_sources
                WHERE profile_id IS NOT NULL
                ORDER BY name
            """),
            conn,
        )
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

CADENCE_LABELS = {"monthly": "Monthly", "semi_monthly": "Semi-Monthly", "biweekly": "Biweekly"}
PERIOD_LABELS = {"weeks": "wk", "months": "mo", "years": "yr"}


def _freq_label(unit: str, count: int) -> str:
    label = PERIOD_LABELS.get(unit, unit)
    return f"every {count} {label}" if count != 1 else f"/{label}"


bills_by_profile: dict[str, pd.DataFrame] = {}
if not bills_df.empty:
    for pid, grp in bills_df.groupby("profile_id"):
        bills_by_profile[pid] = grp.reset_index(drop=True)

income_by_profile: dict[str, list[dict]] = {}
for df, kind in [(txn_sources_df, "txn"), (custom_sources_df, "custom")]:
    if df.empty:
        continue
    for pid, grp in df.groupby("profile_id"):
        if pid not in income_by_profile:
            income_by_profile[pid] = []
        for _, row in grp.iterrows():
            if kind == "txn":
                income_by_profile[pid].append({
                    "name": row["alias"],
                    "cadence": CADENCE_LABELS.get(row["cadence"], row["cadence"]),
                    "active": row["active"],
                })
            else:
                income_by_profile[pid].append({
                    "name": row["name"],
                    "cadence": CADENCE_LABELS.get(row["cadence"], row["cadence"]),
                    "active": row["active"],
                })

bill_count_map = {pid: len(df) for pid, df in bills_by_profile.items()}
income_count_map = {pid: len(srcs) for pid, srcs in income_by_profile.items()}

# ── Profile cards ──────────────────────────────────────────────────────────────

if profiles.empty:
    st.info("No profiles yet. Create one below.")
else:
    for _, p in profiles.iterrows():
        pid = str(p["id"])
        default_badge = " 🏷️ *default*" if p["is_default"] else ""
        bills_n = bill_count_map.get(pid, 0)
        income_n = income_count_map.get(pid, 0)

        with st.expander(
            f"**{p['name']}**{default_badge}  —  {bills_n} bill(s) · {income_n} income source(s)",
            expanded=False,
        ):
            if p["description"]:
                st.caption(p["description"])

            profile_bills = bills_by_profile.get(pid, pd.DataFrame())
            profile_income = income_by_profile.get(pid, [])

            left, right = st.columns(2)

            with left:
                st.markdown("**Bills**")
                if profile_bills.empty:
                    st.caption("No bills linked.")
                else:
                    for _, b in profile_bills.iterrows():
                        active_tag = "" if b["active"] else " *(inactive)*"
                        freq = _freq_label(b["frequency"], int(b["frequency_count"] or 1))
                        st.markdown(
                            f"- {b['name']}{active_tag} — "
                            f"${float(b['amount']):,.2f} {freq} "
                            f"*(${float(b['monthly_equivalent']):,.2f}/mo)*"
                        )

            with right:
                st.markdown("**Income Sources**")
                if not profile_income:
                    st.caption("No income sources linked.")
                else:
                    for src in profile_income:
                        active_tag = "" if src["active"] else " *(inactive)*"
                        st.markdown(f"- {src['name']}{active_tag} — {src['cadence']}")

            st.markdown("---")

            e1, e2 = st.columns(2)
            with e1:
                new_name = st.text_input("Name", value=p["name"], key=f"pname_{pid}")
            with e2:
                new_desc = st.text_area(
                    "Description", value=p["description"] or "", key=f"pdesc_{pid}", height=68
                )

            sc1, sc2, sc3 = st.columns([1, 1, 2])
            with sc1:
                if st.button("💾 Save", key=f"psave_{pid}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("""
                                    UPDATE budgetlens.profiles
                                    SET name = :name, description = :desc
                                    WHERE id = :id
                                """),
                                {"name": new_name, "desc": new_desc or None, "id": pid},
                            )
                        st.success("Saved.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")
            with sc2:
                if not p["is_default"]:
                    if st.button("Set as Default", key=f"pdefault_{pid}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(text("UPDATE budgetlens.profiles SET is_default = FALSE"))
                                conn.execute(
                                    text("UPDATE budgetlens.profiles SET is_default = TRUE WHERE id = :id"),
                                    {"id": pid},
                                )
                            st.success(f"**{p['name']}** is now the default profile.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
            with sc3:
                if st.button("🗑️ Delete", key=f"pdel_{pid}"):
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(
                                text("DELETE FROM budgetlens.profiles WHERE id = :id"),
                                {"id": pid},
                            )
                        st.success(f"Deleted profile **{p['name']}**.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

st.markdown("---")

# ── Add Profile ────────────────────────────────────────────────────────────────

st.subheader("Add Profile")

if "profile_form_gen" not in st.session_state:
    st.session_state["profile_form_gen"] = 0
_gen = st.session_state["profile_form_gen"]

p1, p2 = st.columns(2)
with p1:
    new_profile_name = st.text_input(
        "Name *", placeholder="e.g. Joint, Personal, Side Hustle", key=f"pf_name_{_gen}"
    )
with p2:
    new_profile_desc = st.text_area(
        "Description", placeholder="Optional notes about this profile",
        key=f"pf_desc_{_gen}", height=68,
    )

make_default = st.checkbox("Set as default", value=profiles.empty, key=f"pf_default_{_gen}")

b1, b2 = st.columns([1, 5])
with b1:
    if st.button("➕ Add Profile", type="primary", key="add_profile_submit"):
        if not new_profile_name:
            st.error("Name is required.")
        else:
            try:
                with get_engine().begin() as conn:
                    if make_default:
                        conn.execute(text("UPDATE budgetlens.profiles SET is_default = FALSE"))
                    conn.execute(
                        text("""
                            INSERT INTO budgetlens.profiles (name, description, is_default)
                            VALUES (:name, :desc, :def)
                        """),
                        {"name": new_profile_name, "desc": new_profile_desc or None, "def": make_default},
                    )
                st.success(f"Profile **{new_profile_name}** created.")
                st.session_state["profile_form_gen"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
with b2:
    if st.button("🗑️ Clear", key="clear_profile_form"):
        st.session_state["profile_form_gen"] += 1
        st.rerun()
