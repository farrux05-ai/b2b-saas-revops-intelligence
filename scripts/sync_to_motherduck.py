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
    "main_elementary",  # dbt Elementary observability tables
]



def sync_to_motherduck():
    if not MOTHERDUCK_TOKEN:
        raise ValueError("MOTHERDUCK_TOKEN is not set in .env file!")

    os.environ["MOTHERDUCK_TOKEN"] = MOTHERDUCK_TOKEN
    try:
        print("☁️  Connecting to MotherDuck...")
        # Connecting directly to MotherDuck
        md_con = duckdb.connect(MOTHERDUCK_DB)
    except Exception as e:
        print("\n" + "="*85)
        print("⚠️  WARNING: MotherDuck connection failed.")
        print(f"Error details: {e}")
        print("="*85 + "\n")
        if os.getenv("MOTHERDUCK_REQUIRED", "false").lower() == "true":
            print("❌ MOTHERDUCK_REQUIRED is set to true! Raising connection exception.")
            raise e
        print("Skipping MotherDuck cloud synchronization. Pipeline will continue using local DuckDB.")
        return

    print(f"🔗 Attaching local database: {LOCAL_DB}")
    # ATTACH the local database to the MotherDuck connection
    # This allows direct SQL-level copying without loading data into Python RAM
    md_con.execute(f"ATTACH '{LOCAL_DB}' AS local_db (READ_ONLY)")

    # Get schemas from the ATTACHED local database
    local_schemas = md_con.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE catalog_name = 'local_db'"
    ).df()["schema_name"].tolist()

    print(f"📦 Local schemas found: {local_schemas}")

    schemas_to_sync = sorted(
        [s for s in local_schemas if s in SCHEMAS_TO_COPY],
        key=lambda x: SCHEMAS_TO_COPY.index(x)
    )
    print(f"📤 Syncing schemas: {schemas_to_sync}")

    total_tables = 0
    for schema in schemas_to_sync:
        # Get all tables in this schema in the ATTACHED local DB
        tables_query = f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = '{schema}' AND table_catalog = 'local_db'
        """
        tables = md_con.execute(tables_query).df()["table_name"].tolist()

        print(f"\n  📂 Schema: {schema} ({len(tables)} tables)")

        # Ensure schema exists in MotherDuck
        md_con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        for table in tables:
            try:
                print(f"    🚀 Syncing {schema}.{table}...", end="", flush=True)
                
                # NATIVE COPY: Atomic and memory-efficient
                # 'CREATE OR REPLACE' ensures the table is never missing if the sync fails midway
                sync_query = f"""
                    CREATE OR REPLACE TABLE "{schema}"."{table}" 
                    AS SELECT * FROM local_db."{schema}"."{table}"
                """
                md_con.execute(sync_query)
                
                # Verify row count for logging
                row_count = md_con.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()[0]
                print(f" DONE ({row_count:,} rows)")
                
                total_tables += 1
            except Exception as e:
                print(f" FAILED — {e}")

    md_con.execute("DETACH local_db")
    md_con.close()

    print(f"\n🎉 Done! {total_tables} tables synced to MotherDuck natively.")
    print(f"🔗 View your data at: https://app.motherduck.com")


if __name__ == "__main__":
    sync_to_motherduck()
