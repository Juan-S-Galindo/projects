from __future__ import annotations
import hashlib
import pandas as pd
from sqlalchemy import text
from ..db.connection import get_engine
from .detector import detect_format
from .chase_parser import parse_chase
from .boa_parser import parse_boa


def _compute_hash(row: pd.Series) -> str:
    key = f"{row['source']}|{row['transaction_date']}|{row['description']}|{row['amount']}"
    return hashlib.sha256(key.encode()).hexdigest()


def _fetch_existing_hashes(conn) -> set[str]:
    result = conn.execute(text("SELECT content_hash FROM budgetlens.transactions WHERE content_hash IS NOT NULL"))
    return {row[0] for row in result}


def parse_file(file_bytes: bytes) -> tuple[str, pd.DataFrame]:
    """Returns (source, dataframe) without touching the DB."""
    source = detect_format(file_bytes)
    df = parse_chase(file_bytes) if source == "chase" else parse_boa(file_bytes)
    df["content_hash"] = df.apply(_compute_hash, axis=1)
    return source, df


def ingest(df: pd.DataFrame) -> dict[str, int]:
    """Insert new-only rows (by content_hash) into budgetlens.transactions."""
    engine = get_engine()
    with engine.begin() as conn:
        existing = _fetch_existing_hashes(conn)
        new_df = df[~df["content_hash"].isin(existing)].copy()

        if new_df.empty:
            return {"total": len(df), "imported": 0, "duplicates": len(df)}

        rows = new_df.to_dict(orient="records")
        conn.execute(
            text("""
                INSERT INTO budgetlens.transactions
                    (source, transaction_date, post_date, description, original_description,
                     category, category_overridden, transaction_type, amount, memo,
                     running_balance, bill_id, content_hash)
                VALUES
                    (:source, :transaction_date, :post_date, :description, :original_description,
                     :category, :category_overridden, :transaction_type, :amount, :memo,
                     :running_balance, :bill_id, :content_hash)
            """),
            rows,
        )

    return {
        "total": len(df),
        "imported": len(new_df),
        "duplicates": len(df) - len(new_df),
    }
