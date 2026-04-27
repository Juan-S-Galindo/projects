"""Entry point for the Bank of America checking account CSV ingestor.

Scans apps/boa_ingestor/statements/main/ and apps/boa_ingestor/statements/bills/
for CSV files and ingests each one, tagging rows with the appropriate source.

Usage:
    python -m apps.boa_ingestor.main

Required environment variables:
    PGHOST, PGUSER
Optional environment variables:
    PGPASSWORD
    PGPORT     (default: 5432)
    PGDATABASE (default: expenses)
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

import psycopg2

from apps.boa_ingestor import db, ingestor

STATEMENTS_DIR = Path(__file__).parent / "statements"

# Map each subdirectory to its source tag.
SOURCE_SUBDIRS: List[Tuple[str, str]] = [
    ("main", "MAIN"),
    ("bills", "BILLS"),
]


def _collect_csv_files() -> List[Tuple[Path, str]]:
    """Return a sorted list of (csv_path, source) pairs from both subdirs."""
    collected: List[Tuple[Path, str]] = []
    for subdir_name, source in SOURCE_SUBDIRS:
        subdir = STATEMENTS_DIR / subdir_name
        if not subdir.is_dir():
            continue
        for csv_path in sorted(subdir.glob("*.[Cc][Ss][Vv]")):
            collected.append((csv_path, source))
    return collected


def main() -> None:
    missing = [v for v in ("PGHOST", "PGUSER") if not os.environ.get(v)]
    if missing:
        print(
            f"Error: missing required environment variable(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    csv_files = _collect_csv_files()
    if not csv_files:
        print(
            f"No CSV files found under {STATEMENTS_DIR}/main or {STATEMENTS_DIR}/bills. "
            "Nothing to ingest."
        )
        sys.exit(0)

    print(f"Found {len(csv_files)} CSV file(s) to ingest.")

    try:
        db.setup()
    except psycopg2.OperationalError as exc:
        print(f"Error: could not connect to PostgreSQL: {exc}", file=sys.stderr)
        sys.exit(1)

    total_rows = 0
    try:
        conn = db.get_connection()
        try:
            for csv_path, source in csv_files:
                total_rows += ingestor.ingest(csv_path, source, conn)
        finally:
            conn.close()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except psycopg2.Error as exc:
        print(f"Error: database operation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Done. Total rows inserted: {total_rows}.")


if __name__ == "__main__":
    main()
