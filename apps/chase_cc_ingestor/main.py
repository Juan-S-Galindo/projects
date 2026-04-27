"""Entry point for the Chase credit card CSV ingestor.

Usage:
    python -m apps.chase_cc_ingestor.main <path-to-chase-export.csv>

Required environment variables:
    PGHOST, PGUSER, PGPASSWORD
Optional environment variables:
    PGPORT     (default: 5432)
    PGDATABASE (default: expenses)
"""

import argparse
import sys
from pathlib import Path

import psycopg2

from apps.chase_cc_ingestor import db, ingestor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a Chase credit card CSV export into PostgreSQL."
    )
    parser.add_argument(
        "csv_file",
        metavar="CSV_FILE",
        help="Path to the Chase credit card CSV export file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv_file)

    if not csv_path.exists():
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    if not csv_path.is_file():
        print(f"Error: path is not a file: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Validate required env vars before attempting any DB work.
    missing = [v for v in ("PGHOST", "PGUSER", "PGPASSWORD") if not __import__("os").environ.get(v)]
    if missing:
        print(
            f"Error: missing required environment variable(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        db.setup()
    except psycopg2.OperationalError as exc:
        print(f"Error: could not connect to PostgreSQL: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        conn = db.get_connection()
        try:
            ingestor.ingest(csv_path, conn)
        finally:
            conn.close()
    except ValueError as exc:
        # CSV parsing errors surfaced from ingestor._load_csv
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except psycopg2.Error as exc:
        print(f"Error: database operation failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
