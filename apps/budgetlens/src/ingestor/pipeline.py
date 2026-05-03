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


def parse_file(file_bytes: bytes) -> tuple[str, pd.DataFrame]:
    """Returns (source, dataframe) without touching the DB."""
    source = detect_format(file_bytes)
    df = parse_chase(file_bytes) if source == "chase" else parse_boa(file_bytes)
    df["content_hash"] = df.apply(_compute_hash, axis=1)
    return source, df


def count_already_in_staging(df: pd.DataFrame) -> int:
    """How many rows from df already appear at least once in staging."""
    hashes = df["content_hash"].tolist()
    with get_engine().connect() as conn:
        result = conn.execute(
            text(
                "SELECT COUNT(DISTINCT content_hash) FROM budgetlens.transactions "
                "WHERE content_hash = ANY(:hashes)"
            ),
            {"hashes": hashes},
        )
        return int(result.scalar() or 0)


def ingest(df: pd.DataFrame) -> dict[str, int]:
    """Append all rows to budgetlens.transactions (staging).

    Every upload is stored regardless of whether the same content_hash already
    exists.  The transactions_deduped view surfaces only the most-recent version
    of each transaction.
    """
    rows = df.to_dict(orient="records")
    with get_engine().begin() as conn:
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
    return {"total": len(df), "imported": len(df)}
