import sys, os, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from src.ingestor.pipeline import parse_file, ingest, count_already_in_staging
from src.categorizer import ALL_CATEGORIES, CATEGORY_LABELS

st.set_page_config(page_title="Import — BudgetLens", layout="wide")
st.title("📥 Import Bank CSV")

st.markdown(
    "Upload one or more **Chase** or **Bank of America** CSV exports. "
    "The format is detected automatically per file. "
    "Re-uploading the same file is safe — deduplication keeps the latest version."
)

uploaded_files = st.file_uploader(
    "Drop CSV files here or click to browse",
    type=None,
    accept_multiple_files=True,
    key="csv_uploader",
)

if not uploaded_files:
    st.info("Supported formats: Chase credit card export · Bank of America checking export")
    st.stop()

# ── Parse all files ────────────────────────────────────────────────────────────

category_options = {CATEGORY_LABELS.get(c, c): c for c in ALL_CATEGORIES}
label_options = list(category_options.keys())

parsed: list[dict] = []

for uploaded in uploaded_files:
    if not uploaded.name.lower().endswith(".csv"):
        st.error(f"`{uploaded.name}` — not a .csv file, skipped.")
        continue

    file_bytes = uploaded.read()
    try:
        source, df = parse_file(file_bytes)
    except ValueError as e:
        st.error(f"`{uploaded.name}` — {e}")
        continue

    parsed.append({"name": uploaded.name, "source": source, "df": df})

if not parsed:
    st.stop()

# ── Per-file preview ───────────────────────────────────────────────────────────

st.markdown("---")

for entry in parsed:
    name = entry["name"]
    source = entry["source"]
    df = entry["df"]

    badge_color = "#1D4ED8" if source == "chase" else "#DC2626"
    badge_label = "Chase" if source == "chase" else "Bank of America"

    st.markdown(
        f'<span style="background:{badge_color};color:#fff;padding:4px 12px;'
        f'border-radius:12px;font-size:0.85rem;font-weight:600">'
        f"✓ {badge_label}</span>&nbsp;&nbsp;"
        f"<strong>{name}</strong> — {len(df)} transactions",
        unsafe_allow_html=True,
    )
    st.markdown("")

    display = df[["transaction_date", "description", "amount", "category"]].copy()
    display["transaction_date"] = display["transaction_date"].astype(str)
    display["category_label"] = display["category"].map(lambda c: CATEGORY_LABELS.get(c, c))

    edited = st.data_editor(
        display.rename(columns={
            "transaction_date": "Date",
            "description": "Description",
            "amount": "Amount ($)",
            "category": "category_id",
            "category_label": "Category",
        }),
        column_config={
            "Date": st.column_config.TextColumn(disabled=True, width="small"),
            "Description": st.column_config.TextColumn(disabled=True, width="large"),
            "Amount ($)": st.column_config.NumberColumn(disabled=True, format="$%.2f", width="small"),
            "category_id": None,
            "Category": st.column_config.SelectboxColumn(
                "Category", options=label_options, width="medium"
            ),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key=f"editor_{name}",
    )

    if edited is not None:
        new_cats = edited["Category"].map(category_options)
        df["category_overridden"] = new_cats.values != df["category"].values
        df["category"] = new_cats.values

    try:
        already = count_already_in_staging(df)
        genuinely_new = len(df) - already
        if already > 0:
            st.caption(
                f"ℹ️ {already} already in staging (new version will be added) · "
                f"{genuinely_new} brand-new"
            )
        else:
            st.caption(f"**{len(df)} new transactions** ready to import.")
    except Exception:
        pass

    st.markdown("---")

# ── Confirm import ─────────────────────────────────────────────────────────────

total_txns = sum(len(e["df"]) for e in parsed)
st.markdown(f"**{len(parsed)} file(s) · {total_txns} total transactions** ready to import.")

if st.button("✅ Confirm Import", type="primary"):
    all_ok = True
    with st.spinner(f"Importing {len(parsed)} file(s)…"):
        for entry in parsed:
            try:
                stats = ingest(entry["df"])
                st.success(
                    f"**{entry['name']}** — imported {stats['imported']} transactions."
                )
            except Exception as e:
                st.error(f"**{entry['name']}** — import failed: {e}")
                all_ok = False

    dbt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dbt")
    dbt_env = {
        **os.environ,
        "PGHOST":     os.environ.get("PGHOST", "localhost"),
        "PGPORT":     os.environ.get("PGPORT", "5432"),
        "PGUSER":     os.environ.get("PGUSER", "postgres"),
        "PGPASSWORD": os.environ.get("PGPASSWORD", ""),
        "PGDATABASE": os.environ.get("PGDATABASE", "expenses"),
    }
    with st.spinner("Running dbt build (models + tests)…"):
        try:
            result = subprocess.run(
                ["dbt", "build", "--project-dir", dbt_dir, "--profiles-dir", dbt_dir],
                capture_output=True,
                text=True,
                timeout=120,
                env=dbt_env,
            )
            dbt_output = result.stdout + result.stderr
            if result.returncode == 0:
                st.success("dbt build passed — deduplicated table rebuilt and all tests green.")
                with st.expander("dbt output", expanded=False):
                    st.code(dbt_output)
            else:
                st.warning(
                    "dbt build failed — imported rows are staged but the "
                    "deduplicated table may be stale. Check output for details."
                )
                with st.expander("dbt output", expanded=True):
                    st.code(dbt_output)
        except FileNotFoundError:
            st.warning(
                "`dbt` not found in PATH — skipping model refresh. "
                "Run `dbt build` manually from `apps/budgetlens/dbt/`."
            )
