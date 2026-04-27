# Chase Credit Card Ingestor

Reads Chase credit card CSV exports and upserts them into a local PostgreSQL `expenses` database.

## Prerequisites

- [Homebrew](https://brew.sh) with PostgreSQL installed (`brew install postgresql@18`)
- [Pants](https://www.pantsbuild.org) build system

## Starting PostgreSQL

```bash
brew services start postgresql@18
```

To stop it later:

```bash
brew services stop postgresql@18
```

## Configuration

The app reads connection parameters from environment variables:

| Variable     | Required | Default    | Description          |
|--------------|----------|------------|----------------------|
| `PGHOST`     | Yes      | —          | PostgreSQL hostname  |
| `PGUSER`     | Yes      | —          | PostgreSQL username  |
| `PGPASSWORD` | No       | —          | Password (omit for peer/trust auth) |
| `PGPORT`     | No       | `5432`     | PostgreSQL port      |
| `PGDATABASE` | No       | `expenses` | Target database name |

Example for a local Homebrew install (peer auth, no password needed):

```bash
export PGHOST=localhost
export PGUSER=$(whoami)
```

## Adding Statements

Drop Chase CSV exports into the `statements/` directory:

```
apps/chase_cc_ingestor/statements/
├── BUILD          ← tracked by git
├── jan_2025.csv   ← ignored by git
└── feb_2025.csv   ← ignored by git
```

All `*.csv` files in that directory are picked up automatically on each run.

## Running

```bash
pants run apps/chase_cc_ingestor:chase_cc_ingestor
```

The app will:
1. Scan `statements/` for CSV files
2. Create the `chase_credit_card_transactions` table if it doesn't exist
3. Upsert each row (duplicates across overlapping exports are skipped)
4. Print a summary of total rows inserted
