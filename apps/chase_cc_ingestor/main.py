"""Entry point for the Chase credit card CSV ingestor.

Scans apps/chase_cc_ingestor/statements/ for CSV files and ingests each one.

Usage:
    python -m apps.chase_cc_ingestor.main

Required environment variables:
    PGHOST, PGUSER, PGPASSWORD
Optional environment variables:
    PGPORT     (default: 5432)
    PGDATABASE (default: expenses)
"""

import os
import sys
from pathlib import Path

import psycopg2

from apps.chase_cc_ingestor import db, ingestor

STATEMENTS_DIR = Path(__file__).parent / "statements"


def main() -> None:
    missing = [v for v in ("PGHOST", "PGUSER") if not os.environ.get(v)]
    if missing:
        print(
            f"Error: missing required environment variable(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    csv_files = sorted(STATEMENTS_DIR.glob("*.[Cc][Ss][Vv]"))
    if not csv_files:
        print(f"No CSV files found in {STATEMENTS_DIR}. Nothing to ingest.")
        sys.exit(0)

    print(f"Found {len(csv_files)} CSV file(s) in {STATEMENTS_DIR}.")

    try:
        db.setup()
    except psycopg2.OperationalError as exc:
        print(f"Error: could not connect to PostgreSQL: {exc}", file=sys.stderr)
        sys.exit(1)

    total_rows = 0
    try:
        conn = db.get_connection()
        try:
            for csv_path in csv_files:
                total_rows += ingestor.ingest(csv_path, conn)
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
