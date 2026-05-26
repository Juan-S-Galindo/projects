from __future__ import annotations
import hashlib
import pandas as pd
from sqlalchemy import text
from ..db.connection import get_engine
from .detector import detect_format
from .chase_parser import parse_chase
from .boa_parser import parse_boa


def _compute_hash(row: pd.Series) -> str:
    # row_index is included so two identical transactions on the same day
    # get distinct content_hashes while re-uploading the same file is stable.
    key = (
        f"{row['source']}|{row['transaction_date']}|{row['description']}"
        f"|{row['amount']}|{int(row['row_index'])}"
    )
    return hashlib.sha256(key.encode()).hexdigest()


def _compute_txn_hash(row: pd.Series) -> str:
    # Natural dedup key: no row_index, so the same real-world transaction
    # always produces the same hash regardless of import order or file position.
    key = (
        f"{row['source']}|{row['transaction_date']}|{row['description']}"
        f"|{float(row['amount']):.2f}"
    )
    return hashlib.md5(key.encode()).hexdigest()


def parse_file(file_bytes: bytes) -> tuple[str, pd.DataFrame]:
    """Returns (source, dataframe) without touching the DB."""
    source = detect_format(file_bytes)
    df = parse_chase(file_bytes) if source == "chase" else parse_boa(file_bytes)
    df = df.reset_index(drop=True)
    df["row_index"] = df.index  # 0-based position within this file
    df["content_hash"] = df.apply(_compute_hash, axis=1)
    df["txn_hash"] = df.apply(_compute_txn_hash, axis=1)
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
                     running_balance, bill_id, content_hash, txn_hash)
                VALUES
                    (:source, :transaction_date, :post_date, :description, :original_description,
                     :category, :category_overridden, :transaction_type, :amount, :memo,
                     :running_balance, :bill_id, :content_hash, :txn_hash)
            """),
            rows,
        )
    return {"total": len(df), "imported": len(df)}
