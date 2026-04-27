"""Chase credit card CSV ingestor.

Reads a Chase-format CSV export and appends its rows to
`staging.chase_transactions`.  Rows are never deleted or replaced —
each invocation only adds new rows.

Expected CSV columns (Chase standard export as of 2025):
  Transaction Date, Post Date, Description, Category, Type, Amount, Memo
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import psycopg2.extensions

CHASE_DATE_FORMAT = "%m/%d/%Y"

INSERT_SQL = """
INSERT INTO staging.chase_transactions
    (transaction_date, post_date, description, category, type, amount, memo)
VALUES
    (%s, %s, %s, %s, %s, %s, %s)
"""


def _parse_date(value: str):
    """Parse a Chase date string (MM/DD/YYYY) into a Python date object."""
    return datetime.strptime(value.strip(), CHASE_DATE_FORMAT).date()


def _load_csv(csv_path: Path) -> List[Tuple]:
    """Parse *csv_path* and return a list of row tuples ready for insertion."""
    rows: List[Tuple] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for line_num, row in enumerate(reader, start=2):  # 1-based; row 1 is header
            try:
                rows.append((
                    _parse_date(row["Transaction Date"]),
                    _parse_date(row["Post Date"]),
                    row["Description"].strip(),
                    row.get("Category", "").strip() or None,
                    row.get("Type", "").strip() or None,
                    row["Amount"].strip(),
                    row.get("Memo", "").strip() or None,
                ))
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"Failed to parse CSV row {line_num}: {exc}"
                ) from exc
    return rows


def ingest(csv_path: Path, conn: psycopg2.extensions.connection) -> int:
    """Ingest *csv_path* into `staging.chase_transactions`.

    Parameters
    ----------
    csv_path:
        Path to the Chase CSV export file.
    conn:
        An open psycopg2 connection to the target database.  The connection
        is NOT closed by this function — the caller manages its lifecycle.

    Returns
    -------
    int
        Number of rows inserted.
    """
    rows = _load_csv(csv_path)
    if not rows:
        print("CSV file contains no data rows. Nothing inserted.")
        return 0

    with conn:
        with conn.cursor() as cur:
            cur.executemany(INSERT_SQL, rows)

    row_count = len(rows)
    print(f"Inserted {row_count} row(s) from '{csv_path}' into staging.chase_transactions.")
    return row_count
