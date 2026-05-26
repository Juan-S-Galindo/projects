from __future__ import annotations
import io
import pandas as pd
from ..categorizer import auto_categorize


def parse_chase(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(
        io.BytesIO(file_bytes),
        parse_dates=["Transaction Date", "Post Date"],
        dtype={"Memo": str},
    )

    # Normalize column names
    df = df.rename(columns={
        "Transaction Date": "transaction_date",
        "Post Date": "post_date",
        "Description": "description",
        "Category": "chase_category",
        "Type": "transaction_type",
        "Amount": "amount",
        "Memo": "memo",
    })

    df["source"] = "chase"
    df["original_description"] = df["description"]
    df["transaction_type"] = df["transaction_type"].str.lower().fillna("unknown")
    df["memo"] = df["memo"].where(df["memo"].notna() & (df["memo"] != "nan"), None)

    df["category"] = df.apply(
        lambda r: auto_categorize(r["description"], r.get("chase_category")), axis=1
    )
    df["category_overridden"] = False
    df["running_balance"] = None
    df["bill_id"] = None

    # Convert dates to date objects
    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.date
    df["post_date"] = pd.to_datetime(df["post_date"]).dt.date

    return df[[
        "source", "transaction_date", "post_date", "description",
        "original_description", "category", "category_overridden",
        "transaction_type", "amount", "memo", "running_balance", "bill_id",
    ]]
