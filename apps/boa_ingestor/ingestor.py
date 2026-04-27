"""Bank of America checking account CSV ingestor.

Reads a BofA-format CSV export (with a 6-row preamble) and appends its rows
to `staging.bank_of_america_transactions`.  Rows are never deleted or replaced
— each invocation only adds new rows.

Expected CSV format after the preamble:
  Date, Description, Amount, Running Bal.

The first 6 rows (preamble + blank line) are skipped by scanning for the real
header line.  Rows with a blank Amount field are also skipped.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import psycopg2.extensions

BOA_DATE_FORMAT = "%m/%d/%Y"
REAL_HEADER_FIRST_FIELD = "Date"

INSERT_SQL = """
INSERT INTO staging.bank_of_america_transactions
    (transaction_date, description, amount, running_balance, source)
VALUES
    (%s, %s, %s, %s, %s)
"""


def _parse_date(value: str):
    """Parse a BofA date string (MM/DD/YYYY) into a Python date object."""
    return datetime.strptime(value.strip(), BOA_DATE_FORMAT).date()


def _strip_commas(value: str) -> str:
    """Remove thousands-separator commas from a numeric string."""
    return value.replace(",", "")


def _load_csv(csv_path: Path, source: str) -> List[Tuple]:
    """Parse *csv_path* and return a list of row tuples ready for insertion.

    Parameters
    ----------
    csv_path:
        Path to the BofA CSV export file.
    source:
        Account source tag — either ``"MAIN"`` or ``"BILLS"``.
    """
    rows: List[Tuple] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        # Scan past the preamble until we find the real header row.
        real_header_line: str | None = None
        for raw_line in fh:
            if raw_line.strip().startswith(REAL_HEADER_FIRST_FIELD + ","):
                real_header_line = raw_line
                break

        if real_header_line is None:
            raise ValueError(
                f"Could not find the data header row in '{csv_path}'. "
                "Expected a line starting with 'Date,'."
            )

        # Feed the header line and the rest of the file into DictReader.
        import io
        remaining = real_header_line + fh.read()
        reader = csv.DictReader(io.StringIO(remaining))

        for line_num, row in enumerate(reader, start=2):  # 1-based; row 1 is the header
            amount_raw = row.get("Amount", "").strip()
            if not amount_raw:
                # Skip rows with no amount (e.g. beginning-balance summary row).
                continue

            running_bal_raw = row.get("Running Bal.", "").strip()

            try:
                rows.append((
                    _parse_date(row["Date"]),
                    row["Description"].strip(),
                    float(_strip_commas(amount_raw)),
                    float(_strip_commas(running_bal_raw)) if running_bal_raw else None,
                    source,
                ))
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"Failed to parse CSV row {line_num} in '{csv_path}': {exc}"
                ) from exc

    return rows


def ingest(csv_path: Path, source: str, conn: psycopg2.extensions.connection) -> int:
    """Ingest *csv_path* into `staging.bank_of_america_transactions`.

    Parameters
    ----------
    csv_path:
        Path to the BofA CSV export file.
    source:
        Account source tag — either ``"MAIN"`` or ``"BILLS"``.
    conn:
        An open psycopg2 connection to the target database.  The connection
        is NOT closed by this function — the caller manages its lifecycle.

    Returns
    -------
    int
        Number of rows inserted.
    """
    rows = _load_csv(csv_path, source)
    if not rows:
        print(f"  '{csv_path.name}': no data rows found. Nothing inserted.")
        return 0

    with conn:
        with conn.cursor() as cur:
            cur.executemany(INSERT_SQL, rows)

    row_count = len(rows)
    print(
        f"  '{csv_path.name}' [{source}]: inserted {row_count} row(s) into "
        "staging.bank_of_america_transactions."
    )
    return row_count
