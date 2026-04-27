"""Database setup for the Chase credit card ingestor.

Reads connection parameters from environment variables:
  PGHOST       — hostname (required)
  PGPORT       — port (default: 5432)
  PGUSER       — username (required)
  PGPASSWORD   — password (optional)
  PGDATABASE   — target database name (default: expenses)

On startup:
  1. Connects to the default `postgres` database to CREATE the target
     database if it does not already exist.
  2. Connects to the target database and creates the `staging` schema and
     the `staging.chase_transactions` table if they do not already exist.
"""

import os

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def _connection_params(database: str) -> dict:
    """Build a psycopg2 connection keyword-argument dict for *database*."""
    return {
        "host": os.environ["PGHOST"],
        "port": int(os.environ.get("PGPORT", 5432)),
        "user": os.environ["PGUSER"],
        "password": os.environ.get("PGPASSWORD") or None,
        "database": database,
    }


def _target_database() -> str:
    return os.environ.get("PGDATABASE", "expenses")


def ensure_database_exists() -> None:
    """Create the target database if it does not exist.

    Must connect to the `postgres` maintenance database first because
    CREATE DATABASE cannot run inside a transaction block.
    """
    target_db = _target_database()
    conn = psycopg2.connect(**_connection_params("postgres"))
    try:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (target_db,),
            )
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(target_db)
                    )
                )
                print(f"Created database '{target_db}'.")
            else:
                print(f"Database '{target_db}' already exists.")
    finally:
        conn.close()


CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS staging"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS staging.chase_transactions (
    id               SERIAL PRIMARY KEY,
    transaction_date DATE          NOT NULL,
    post_date        DATE          NOT NULL,
    description      TEXT          NOT NULL,
    category         TEXT,
    type             TEXT,
    amount           NUMERIC(12,2) NOT NULL,
    memo             TEXT,
    ingested_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
)
"""


def ensure_schema_and_table() -> None:
    """Create the `staging` schema and `chase_transactions` table if absent."""
    conn = psycopg2.connect(**_connection_params(_target_database()))
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SCHEMA_SQL)
                cur.execute(CREATE_TABLE_SQL)
        print("Schema and table are ready.")
    finally:
        conn.close()


def setup() -> None:
    """Run all database setup steps in order."""
    ensure_database_exists()
    ensure_schema_and_table()


def get_connection() -> psycopg2.extensions.connection:
    """Return an open psycopg2 connection to the target database.

    The caller is responsible for closing or using it as a context
    manager.
    """
    return psycopg2.connect(**_connection_params(_target_database()))
