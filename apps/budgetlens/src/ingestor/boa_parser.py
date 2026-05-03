from __future__ import annotations
import io
import pandas as pd
from ..categorizer import auto_categorize


def parse_boa(file_bytes: bytes) -> pd.DataFrame:
    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # Find the real header line: starts with "Date,"
    header_idx = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("Date,")),
        None,
    )
    if header_idx is None:
        raise ValueError("Could not find header row in BOA CSV (expected a line starting with 'Date,')")

    data_text = "\n".join(lines[header_idx:])
    df = pd.read_csv(
        io.StringIO(data_text),
        dtype=str,  # read everything as string first so we can strip commas
    )

    df = df.rename(columns={
        "Date": "transaction_date",
        "Description": "description",
        "Amount": "amount",
        "Running Bal.": "running_balance",
    })

    # Strip commas from numeric columns and convert
    def clean_numeric(series: pd.Series) -> pd.Series:
        return pd.to_numeric(
            series.str.replace(",", "", regex=False),
            errors="coerce",
        )

    df["amount"] = clean_numeric(df["amount"])
    df["running_balance"] = clean_numeric(df.get("running_balance", pd.Series(dtype=str)))

    # Drop rows with no amount (e.g., "Beginning balance" summary row)
    df = df.dropna(subset=["amount"])
    # Also drop pure balance / beginning rows by description
    df = df[~df["description"].str.lower().str.startswith("beginning balance", na=False)]

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], format="%m/%d/%Y").dt.date

    df["source"] = "boa"
    df["original_description"] = df["description"]
    df["category"] = df["description"].apply(auto_categorize)
    df["category_overridden"] = False
    df["transaction_type"] = df["description"].apply(
        lambda d: "transfer" if "transfer" in d.lower() else "unknown"
    )
    df["post_date"] = None
    df["memo"] = None
    df["bill_id"] = None

    return df[[
        "source", "transaction_date", "post_date", "description",
        "original_description", "category", "category_overridden",
        "transaction_type", "amount", "memo", "running_balance", "bill_id",
    ]]
