"""
dagster_pipeline.py
===================
SentinelGuard B2B SaaS — RevOps Intelligence Engine
Orchestration layer: Dagster manages the full ELT pipeline lifecycle.

DATA FLOW:
  [1] ingestion_dlt      — External sources (API/JSON) → DuckDB raw_data
  [2] revops_dbt_assets  — raw_data → staging → intermediate → marts
  [3] motherduck_sync    — Local DuckDB → MotherDuck Cloud
  [4] dlt_reverse_etl    — marts (DuckDB) → HubSpot CRM

KEY ARCHITECTURAL DECISIONS:
  - Monitoring: Every asset reports its status and failures in the Dagster UI.
  - RetryPolicy: Exponential backoff handles temporary network/API errors gracefully.
  - Declarative Lineage: Dagster manages dependencies and execution order using AssetSelection.all().
  - Portability: shutil.which() dynamically resolves dbt executable path locally and in Cloud Docker containers.
  - Security: All credentials use os.getenv(), integrated with local .env and Dagster Cloud Secrets.
"""

import os
import shutil
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    Backoff,
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster_dbt import DbtCliResource, dbt_assets

from ingestion.stackflow_pipeline import run_pipeline as run_ingestion
from scripts.reverse_etl_dlt import run as run_reverse_etl_sync
from scripts.sync_to_motherduck import sync_to_motherduck as run_motherduck_sync

# ===========================================================================
# PATHS & CONFIGURATION
# Path(__file__).parent gets the directory of this file.
# .resolve() turns a relative path into an absolute one.
# ===========================================================================

DBT_PROJECT_DIR = Path(__file__).parent.resolve()

# shutil.which("dbt") works like the Linux `which dbt` command.
# Local dev: resolved via .venv/bin/dbt | Docker/Cloud: resolved via global path.
_dbt_executable = shutil.which("dbt") or str(
    DBT_PROJECT_DIR / ".venv" / "bin" / "dbt"
)

# ===========================================================================
# LAYER 1: EXTRACT & LOAD — Ingestion
#
# Function:
#   Ingests HubSpot, Stripe, Zendesk, and Internal DB raw data into DuckDB raw_data schema.
#
# NOTE FOR PRODUCTION:
#   This project uses mock raw JSON files for local development.
#   In production, these read directly from external APIs:
#     hubspot_source(api_key=os.getenv("HUBSPOT_API_KEY"))
#   using write_disposition="merge" and incremental tracking.
#
# RetryPolicy:
#   max_retries=3  → Retry up to 3 times on failure
#   delay=60       → Wait 60 seconds before retrying
#   backoff=EXPONENTIAL → Exponentially increase wait time (60s → 120s → 240s)
# ===========================================================================

@asset(
    group_name="ingestion",
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=60,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Loads HubSpot, Stripe, Zendesk, and Internal raw data into DuckDB raw_data schema.",
)
def ingestion_dlt(context: AssetExecutionContext):
    context.log.info("▶ 1/4 — Starting dlt ingestion...")
    context.log.info("  Sources: HubSpot | Stripe | Zendesk | Internal DB")
    run_ingestion()
    context.log.info("✅ dlt ingestion completed successfully.")


# ===========================================================================
# LAYER 2: TRANSFORM — dbt
#
# Function:
#   1. `dbt source freshness` — Checks if raw source tables are stale (older than 24 hours).
#      If sources are stale, it raises an error and stops the pipeline.
#      This prevents stale inputs from corrupting downstream models.
#
#   2. `dbt build --store-failures` — Builds and tests staging, intermediate, and mart models.
#      --store-failures: saves failing test rows to DuckDB for easier debugging.
#
# NOTE: @dbt_assets reads manifest.json to expose dbt models as individual assets in Dagster.
#   This enables rich lineage graphs and model-level monitoring in the UI.
#
# deps=ingestion_dlt:
#   Forces Dagster to run the dlt ingestion step BEFORE running dbt models.
# ===========================================================================

@dbt_assets(
    manifest=DBT_PROJECT_DIR / "target" / "manifest.json",
)
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Builds and tests all dbt models (staging -> intermediate -> marts)."""

    context.log.info("▶ 2/4 — Running dbt source freshness checks...")
    # First, run source freshness to verify data is recent.
    yield from dbt.cli(["source", "freshness"], context=context).stream()

    context.log.info("✅ Source freshness checks passed. Running dbt build...")
    # Run dbt build (includes seeds, snapshots, runs, and tests) and store failures.
    yield from dbt.cli(["build", "--store-failures"], context=context).stream()

    context.log.info("✅ dbt build completed successfully.")



# ===========================================================================
# LAYER 4: SYNC — MotherDuck Cloud
#
# Function:
#   Copies raw_data, main_staging, and main_marts schemas from local DuckDB
#   to MotherDuck (Cloud) using native ATTACH + CREATE OR REPLACE statements.
#
# WHY ATTACH + COPY?
#   Direct dlt-MotherDuck connections can occasionally experience timeouts.
#   Using local DuckDB + SQL ATTACH is highly memory-efficient (no Python RAM buffering)
#   and extremely fast.
#
# deps=[revops_dbt_assets]:
#   Ensures data is fully processed and validated by dbt before syncing to the cloud.
# ===========================================================================

@asset(
    group_name="sync",
    deps=[revops_dbt_assets],
    retry_policy=RetryPolicy(
        max_retries=2,
        delay=30,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Syncs local DuckDB tables to MotherDuck Cloud using ATTACH + COPY.",
)
def motherduck_sync(context: AssetExecutionContext):
    context.log.info("▶ 4/6 — Starting MotherDuck cloud sync...")
    context.log.info(
        f"  MOTHERDUCK_REQUIRED status: {os.getenv('MOTHERDUCK_REQUIRED', 'false')}"
    )
    run_motherduck_sync()
    context.log.info("✅ MotherDuck cloud sync completed successfully.")


# ===========================================================================
# LAYER 4: REVERSE ETL — HubSpot CRM Writeback
#
# Function:
#   Pushes processed CRM insights from the dim_accounts and fct_pql_signals
#   marts back into HubSpot CRM:
#     - Company enrichment: MRR, ARR, health metrics → HubSpot Companies
#     - PQL signals: Intent level, recommended action → HubSpot Contacts
#     - L2A associations: Matches unassociated contacts to company records
#
# WHY AFTER motherduck_sync?
#   Sequenced after cloud sync so that in case the build fails early,
#   we do not upload stale or incorrect data to HubSpot.
# ===========================================================================

@asset(
    group_name="reverse_etl",
    deps=[motherduck_sync],
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=60,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Pushes processed insights (MRR, Health, PQL signals) from DuckDB marts back to HubSpot CRM.",
)
def dlt_reverse_etl(context: AssetExecutionContext):
    context.log.info("▶ 5/6 — Starting Reverse ETL (DuckDB -> HubSpot)...")

    hubspot_token = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
    if not hubspot_token or "xxxx" in hubspot_token:
        context.log.warning(
            "⚠️  HUBSPOT_ACCESS_TOKEN is missing or a placeholder. "
            "Skipping HubSpot Reverse ETL sync. "
            "Please configure the real token in Dagster Cloud Env Vars for production."
        )
        return

    run_reverse_etl_sync()
    context.log.info("✅ Reverse ETL completed successfully.")


# ===========================================================================
# LAYER 5: OBSERVABILITY — Elementary Report Generation
#
# Function:
#   Runs Elementary CLI (edr) to generate a data observability HTML report.
#
# deps=[revops_dbt_assets]:
#   Ensures that dbt has run and updated the observability tables in local DuckDB
#   and generated dbt artifacts under target/ before generating the report.
# ===========================================================================

@asset(
    group_name="observability",
    deps=[revops_dbt_assets],
    description="Generates local Elementary data observability HTML report.",
)
def elementary_report(context: AssetExecutionContext):
    context.log.info("▶ 6/6 — Generating Elementary observability report...")
    
    edr_executable = shutil.which("edr") or str(
        DBT_PROJECT_DIR / ".venv" / "bin" / "edr"
    )
    
    import subprocess
    cmd = [
        edr_executable,
        "report",
        "--profiles-dir", os.fspath(DBT_PROJECT_DIR),
        "--project-dir", os.fspath(DBT_PROJECT_DIR),
        "--file-path", os.fspath(DBT_PROJECT_DIR / "docs" / "elementary_report.html")
    ]
    
    context.log.info(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        context.log.error(f"Failed to generate Elementary report:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        raise RuntimeError(f"Elementary report generation failed with exit code {result.returncode}")
        
    context.log.info("✅ Elementary observability report generated successfully at docs/elementary_report.html.")

    # Slack alerting step
    slack_webhook = os.getenv("SLACK_WEBHOOK")
    if slack_webhook:
        context.log.info("▶ Sending Elementary alerts to Slack...")
        monitor_cmd = [
            edr_executable,
            "monitor",
            "--profiles-dir", os.fspath(DBT_PROJECT_DIR),
            "--project-dir", os.fspath(DBT_PROJECT_DIR),
            "--slack-webhook", slack_webhook
        ]
        context.log.info(f"Running command: {' '.join(monitor_cmd)}")
        monitor_result = subprocess.run(
            monitor_cmd,
            capture_output=True,
            text=True
        )
        if monitor_result.returncode != 0:
            context.log.warning(
                f"Elementary monitor failed to send Slack alerts:\n"
                f"STDOUT:\n{monitor_result.stdout}\nSTDERR:\n{monitor_result.stderr}"
            )
        else:
            context.log.info("✅ Elementary alerts sent to Slack successfully.")
    else:
        context.log.info("ℹ️ No SLACK_WEBHOOK environment variable found. Skipping Slack alerts.")


# ===========================================================================
# JOBS
#
# revops_full_pipeline_job:
#   Uses AssetSelection.all() to run all 4 assets in sequence.
#   Dagster automatically manages the execution order based on the lineage.
#
# revops_ingestion_only_job:
#   Runs dlt ingestion only. Useful for manual syncs or debugging.
#
# revops_transform_only_job:
#   Runs dbt transformations and MotherDuck sync without running ingestion.
#   Useful when raw data is already updated and you are iterating on SQL models.
# ===========================================================================

revops_full_pipeline_job = define_asset_job(
    name="revops_full_pipeline_job",
    selection=AssetSelection.all(),
    description="Full ELT pipeline: Ingestion -> dbt -> MotherDuck -> HubSpot Reverse ETL",
)

revops_ingestion_only_job = define_asset_job(
    name="revops_ingestion_only_job",
    selection=AssetSelection.assets(ingestion_dlt),
    description="Runs dlt ingestion only for debugging or manual loads.",
)

revops_transform_only_job = define_asset_job(
    name="revops_transform_only_job",
    selection=AssetSelection.assets(revops_dbt_assets, motherduck_sync),
    description="Runs dbt build and MotherDuck sync only (skips ingestion).",
)


# ===========================================================================
# SCHEDULES
#
# cron_schedule="0 7 * * *" → Runs daily at 07:00 UTC.
#
# execution_timezone="UTC" is used to prevent issues with Daylight Saving Time.
# ===========================================================================

revops_daily_schedule = ScheduleDefinition(
    name="revops_daily_07_utc",
    job=revops_full_pipeline_job,
    cron_schedule="0 7 * * *",
    execution_timezone="UTC",
)


# ===========================================================================
# DEFINITIONS
#
# Declares all assets, jobs, schedules, and resources to the Dagster instance.
# ===========================================================================

defs = Definitions(
    assets=[
        ingestion_dlt,
        revops_dbt_assets,
        motherduck_sync,
        dlt_reverse_etl,
        elementary_report,
    ],
    jobs=[
        revops_full_pipeline_job,
        revops_ingestion_only_job,
        revops_transform_only_job,
    ],
    schedules=[
        revops_daily_schedule,
    ],
    resources={
        "dbt": DbtCliResource(
            project_dir=os.fspath(DBT_PROJECT_DIR),
            dbt_executable=_dbt_executable,
        ),
    },
)
