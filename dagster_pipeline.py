"""
dagster_pipeline.py
===================
SentinelGuard B2B SaaS — RevOps Intelligence Engine
Orchestration layer: Dagster manages the full ELT pipeline lifecycle.

DATA FLOW:
  [1] ingestion_dlt      — External sources (API/JSON) → DuckDB raw_data
  [2] revops_dbt_assets  — raw_data → staging → intermediate → marts (local DuckDB)
  [3] snowflake_sync     — dbt build --target snowflake (Production Warehouse)
  [4] dlt_reverse_etl    — marts (DuckDB) → HubSpot CRM
  [5] elementary_report  — Observability report & Slack alerts

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

# ===========================================================================
# PATHS & CONFIGURATION
# ===========================================================================

DBT_PROJECT_DIR = Path(__file__).parent.resolve()

_dbt_executable = shutil.which("dbt") or str(
    DBT_PROJECT_DIR / ".venv" / "bin" / "dbt"
)

# ===========================================================================
# LAYER 1: EXTRACT & LOAD — Ingestion
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
    context.log.info("▶ 1/5 — Starting dlt ingestion...")
    context.log.info("  Sources: HubSpot | Stripe | Zendesk | Internal DB")
    run_ingestion()
    context.log.info("✅ dlt ingestion completed successfully.")


# ===========================================================================
# LAYER 2: TRANSFORM — dbt (Local DuckDB)
# ===========================================================================

@dbt_assets(
    manifest=DBT_PROJECT_DIR / "target" / "manifest.json",
)
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Builds and tests all dbt models locally on DuckDB (staging -> intermediate -> marts)."""

    context.log.info("▶ 2/5 — Running dbt source freshness checks...")
    yield from dbt.cli(["source", "freshness"], context=context).stream()

    context.log.info("✅ Source freshness checks passed. Running local dbt build...")
    yield from dbt.cli(["build", "--store-failures"], context=context).stream()

    context.log.info("✅ Local dbt build completed successfully.")


# ===========================================================================
# LAYER 3: PRODUCTION DEPLOYMENT — Snowflake Warehouse
#
# Function:
#   Deploys transformed models and runs tests against Snowflake enterprise warehouse.
#   Uses `dbt build --target snowflake` when Snowflake credentials are set in .env.
# ===========================================================================

@asset(
    group_name="sync",
    deps=[revops_dbt_assets],
    retry_policy=RetryPolicy(
        max_retries=2,
        delay=30,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Deploys transformed models and tests to Snowflake Enterprise Warehouse.",
)
def snowflake_sync(context: AssetExecutionContext, dbt: DbtCliResource):
    context.log.info("▶ 3/5 — Starting Snowflake production deployment...")
    account = os.getenv("SNOWFLAKE_ACCOUNT", "")

    if not account or "your_org" in account:
        context.log.warning(
            "⚠️  SNOWFLAKE_ACCOUNT is not configured in .env. "
            "Skipping Snowflake production deployment. "
            "Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD in .env for production."
        )
        return

    context.log.info("Running dbt build against Snowflake...")
    yield from dbt.cli(["build", "--target", "snowflake"], context=context).stream()
    context.log.info("✅ Snowflake production deployment completed successfully.")


# ===========================================================================
# LAYER 4: REVERSE ETL — HubSpot CRM Writeback
# ===========================================================================

@asset(
    group_name="reverse_etl",
    deps=[snowflake_sync],
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=60,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Pushes processed insights (MRR, Health, PQL signals) from DuckDB marts back to HubSpot CRM.",
)
def dlt_reverse_etl(context: AssetExecutionContext):
    context.log.info("▶ 4/5 — Starting Reverse ETL (DuckDB -> HubSpot)...")

    hubspot_token = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
    if not hubspot_token or "xxxx" in hubspot_token:
        context.log.warning(
            "⚠️  HUBSPOT_ACCESS_TOKEN is missing or a placeholder. "
            "Skipping HubSpot Reverse ETL sync."
        )
        return

    run_reverse_etl_sync()
    context.log.info("✅ Reverse ETL completed successfully.")


# ===========================================================================
# LAYER 5: OBSERVABILITY — Elementary Report Generation
# ===========================================================================

@asset(
    group_name="observability",
    deps=[revops_dbt_assets],
    description="Generates local Elementary data observability HTML report.",
)
def elementary_report(context: AssetExecutionContext):
    context.log.info("▶ 5/5 — Generating Elementary observability report...")
    
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
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        context.log.error(f"Failed to generate Elementary report:\n{result.stderr}")
        raise RuntimeError(f"Elementary report generation failed with exit code {result.returncode}")
        
    context.log.info("✅ Elementary observability report generated successfully at docs/elementary_report.html.")

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
        monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
        if monitor_result.returncode != 0:
            context.log.warning(f"Elementary monitor failed: {monitor_result.stderr}")
        else:
            context.log.info("✅ Elementary alerts sent to Slack successfully.")


# ===========================================================================
# JOBS
# ===========================================================================

revops_full_pipeline_job = define_asset_job(
    name="revops_full_pipeline_job",
    selection=AssetSelection.all(),
    description="Full ELT pipeline: Ingestion -> Local dbt -> Snowflake -> HubSpot Reverse ETL",
)

revops_ingestion_only_job = define_asset_job(
    name="revops_ingestion_only_job",
    selection=AssetSelection.assets(ingestion_dlt),
    description="Runs dlt ingestion only for debugging or manual loads.",
)

revops_transform_only_job = define_asset_job(
    name="revops_transform_only_job",
    selection=AssetSelection.assets(revops_dbt_assets, snowflake_sync),
    description="Runs dbt build on local DuckDB and Snowflake.",
)


# ===========================================================================
# SCHEDULES
# ===========================================================================

revops_daily_schedule = ScheduleDefinition(
    name="revops_daily_07_utc",
    job=revops_full_pipeline_job,
    cron_schedule="0 7 * * *",
    execution_timezone="UTC",
)


# ===========================================================================
# DEFINITIONS
# ===========================================================================

defs = Definitions(
    assets=[
        ingestion_dlt,
        revops_dbt_assets,
        snowflake_sync,
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
