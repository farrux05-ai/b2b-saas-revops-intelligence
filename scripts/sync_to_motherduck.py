"""
sync_to_motherduck.py
---------------------
Syncs all tables from the local DuckDB warehouse to MotherDuck (Cloud).

Strategy:
  1. Run local dlt ingestion to populate local DuckDB.
  2. Run dbt to build all mart tables in local DuckDB.
  3. Run this script to COPY everything to MotherDuck.

This avoids the dlt-motherduck connection timeout issue entirely by
using DuckDB's native ATTACH + COPY approach, which is the most
reliable way to push data to MotherDuck.
"""

import os
import duckdb
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = "duckdb/revops_intelligence.duckdb"
MOTHERDUCK_TOKEN = os.getenv("MOTHERDUCK_TOKEN", "")
MOTHERDUCK_DB = "md:revops_intelligence"

# Schemas we want to copy to MotherDuck
SCHEMAS_TO_COPY = [
    "raw_data",         # raw ingested data (dlt output)
    "main_marts",       # dbt mart layer
    "main_staging",     # dbt staging layer (optional)
]


def sync_to_motherduck():
    if not MOTHERDUCK_TOKEN:
        raise ValueError("MOTHERDUCK_TOKEN is not set in .env file!")

    os.environ["MOTHERDUCK_TOKEN"] = MOTHERDUCK_TOKEN

    print("🦆 Connecting to local DuckDB...")
    local_con = duckdb.connect(LOCAL_DB, read_only=True)

    print("☁️  Connecting to MotherDuck...")
    md_con = duckdb.connect(MOTHERDUCK_DB)

    # Get all schemas in local DB
    local_schemas = local_con.execute(
        "SELECT schema_name FROM information_schema.schemata"
    ).df()["schema_name"].tolist()

    print(f"📦 Local schemas found: {local_schemas}")

    schemas_to_sync = [s for s in local_schemas if s in SCHEMAS_TO_COPY]
    print(f"📤 Syncing schemas: {schemas_to_sync}")

    total_tables = 0
    for schema in schemas_to_sync:
        # Get all tables in this schema
        tables = local_con.execute(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"
        ).df()["table_name"].tolist()

        print(f"\n  📂 Schema: {schema} ({len(tables)} tables)")

        # Ensure schema exists in MotherDuck
        md_con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        for table in tables:
            try:
                # Read from local DuckDB
                df = local_con.execute(f'SELECT * FROM "{schema}"."{table}"').df()
                row_count = len(df)

                # Write to MotherDuck (replace existing)
                md_con.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}"')
                md_con.execute(f'CREATE TABLE "{schema}"."{table}" AS SELECT * FROM df')

                print(f"    ✅ {schema}.{table}: {row_count:,} rows uploaded")
                total_tables += 1
            except Exception as e:
                print(f"    ⚠️  {schema}.{table}: SKIPPED — {e}")

    local_con.close()
    md_con.close()

    print(f"\n🎉 Done! {total_tables} tables synced to MotherDuck.")
    print(f"🔗 View your data at: https://app.motherduck.com")


if __name__ == "__main__":
    sync_to_motherduck()
