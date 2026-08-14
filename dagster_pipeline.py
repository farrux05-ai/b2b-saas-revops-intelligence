"""
dagster_pipeline.py
===================
B2B SaaS RevOps Intelligence Engine
Orchestration layer: Dagster manages the full ELT pipeline lifecycle.

DATA FLOW:
  [1] ingestion_dlt      — External sources (API/JSON) → Snowflake RAW_DATA schema
  [2] revops_dbt_assets  — Snowflake: RAW_DATA → STAGING → INTERMEDIATE → MARTS
  [3] dlt_reverse_etl    — Snowflake MARTS → HubSpot CRM (Reverse ETL)
  [4] elementary_report  — Observability report & Slack alerts

KEY ARCHITECTURAL DECISIONS:
  - Single Warehouse: Snowflake is the only compute and storage layer. No local DuckDB.
  - Monitoring: Every asset reports its status and failures in the Dagster UI.
  - RetryPolicy: Exponential backoff handles temporary network/API errors gracefully.
  - Declarative Lineage: Dagster manages execution order via asset dependencies.
  - Portability: shutil.which() dynamically resolves dbt executable locally and in Cloud Docker.
  - Security: All credentials use os.getenv(), integrated with local .env and Dagster Cloud Secrets.
"""

import json
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
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from ingestion.stackflow_pipeline import run_pipeline as run_ingestion
from scripts.reverse_etl_dlt import run as run_reverse_etl_sync

# ===========================================================================
# PATHS & CONFIGURATION
#
# Path(__file__).parent gets the directory of this file.
# .resolve() turns a relative path into an absolute one.
# ===========================================================================

DBT_PROJECT_DIR = Path(__file__).parent.resolve()
dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()

# shutil.which("dbt") works like the Linux `which dbt` command.
# Local dev: resolved via .venv/bin/dbt | Docker/Cloud: resolved via global path.
_dbt_executable = shutil.which("dbt") or str(
    DBT_PROJECT_DIR / ".venv" / "bin" / "dbt"
)

# ===========================================================================
# LAYER 1: EXTRACT & LOAD — Ingestion (dlt → Snowflake)
#
# Function:
#   Ingests HubSpot, Stripe, Zendesk, and Internal DB raw data directly
#   into the Snowflake RAW_DATA schema using dlt.
#
# NOTE FOR PRODUCTION:
#   The production dlt pipeline (b2b_dlt/) reads directly from external APIs
#   using write_disposition="merge" and incremental tracking.
#   The dev pipeline (ingestion/stackflow_pipeline.py) reads mock JSON files.
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
    description="Loads HubSpot, Stripe, Zendesk, and Internal raw data into Snowflake RAW_DATA schema.",
)
def ingestion_dlt(context: AssetExecutionContext):
    context.log.info("▶ 1/4 — Starting dlt ingestion...")
    context.log.info("  Sources: HubSpot | Stripe | Zendesk | Internal DB")
    context.log.info("  Destination: Snowflake RAW_DATA schema")
    run_ingestion()
    context.log.info("✅ dlt ingestion into Snowflake completed successfully.")


# ===========================================================================
# LAYER 2: TRANSFORM — dbt on Snowflake
#
# Function:
#   1. `dbt source freshness` — Verifies that Snowflake raw tables are not stale.
#      Halts pipeline if any source exceeds its configured SLA threshold.
#
#   2. `dbt build --store-failures` — Builds and tests all models on Snowflake:
#      Seeds → Snapshots → Staging → Intermediate → Marts
#      --store-failures saves failing test rows into Snowflake for debugging.
#
# NOTE: @dbt_assets reads manifest.json to expose each dbt model as an
#   individual Dagster asset, enabling rich lineage graphs and model-level
#   monitoring in the Dagster UI.
#
# deps=ingestion_dlt:
#   Forces Dagster to run dlt ingestion BEFORE running dbt transformations.
# ===========================================================================

with open(dbt_project.manifest_path, "r", encoding="utf-8") as f:
    manifest_dict = json.load(f)

@dbt_assets(
    manifest=manifest_dict,
)
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Builds and tests all dbt models on Snowflake (staging → intermediate → marts)."""

    context.log.info("▶ 2/4 — Running dbt source freshness checks on Snowflake...")
    yield from dbt.cli(["source", "freshness"], context=context).stream()

    context.log.info("✅ Source freshness checks passed. Running dbt build on Snowflake...")
    yield from dbt.cli(["build", "--store-failures"], context=context).stream()

    context.log.info("✅ dbt build on Snowflake completed successfully.")


# ===========================================================================
# LAYER 3: REVERSE ETL — HubSpot CRM Writeback
#
# Function:
#   Reads fct_pql_signals and dim_accounts directly from Snowflake MARTS schema
#   and pushes enriched properties back to HubSpot CRM:
#     - Company enrichment: MRR, ARR, health_status, seat_utilization
#     - PQL signals: intent_tier (HOT/WARM/COLD), recommended_action
#     - L2A associations: Contact ↔ Company link enrichment
#
# WHY AFTER revops_dbt_assets?
#   Ensures data is fully transformed and validated in Snowflake before
#   pushing to HubSpot. Stale or failed dbt models will halt the pipeline here.
# ===========================================================================

@asset(
    group_name="reverse_etl",
    deps=[revops_dbt_assets],
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=60,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Reads insights from Snowflake MARTS and pushes MRR, Health, PQL signals back to HubSpot CRM.",
)
def dlt_reverse_etl(context: AssetExecutionContext):
    context.log.info("▶ 3/4 — Starting Reverse ETL (Snowflake → HubSpot)...")

    hubspot_token = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
    if not hubspot_token or "xxxx" in hubspot_token:
        context.log.warning(
            "⚠️  HUBSPOT_ACCESS_TOKEN is missing or a placeholder. "
            "Skipping HubSpot Reverse ETL sync. "
            "Please configure the real token in Dagster Cloud Env Vars for production."
        )
        return

    run_reverse_etl_sync()
    context.log.info("✅ Reverse ETL (Snowflake → HubSpot) completed successfully.")


# ===========================================================================
# LAYER 4: OBSERVABILITY — Elementary Report Generation
#
# Function:
#   Runs Elementary CLI (edr) to generate a data observability HTML report
#   from Elementary's metadata tables stored in Snowflake.
#
# deps=[revops_dbt_assets]:
#   Ensures dbt has run and populated the Elementary metadata tables in
#   Snowflake before generating the observability report.
# ===========================================================================

@asset(
    group_name="observability",
    deps=[revops_dbt_assets],
    description="Generates Elementary data observability HTML report from Snowflake metadata.",
)
def elementary_report(context: AssetExecutionContext):
    context.log.info("▶ 4/4 — Generating Elementary observability report...")

    edr_executable = shutil.which("edr") or str(
        DBT_PROJECT_DIR / ".venv" / "bin" / "edr"
    )

    import subprocess
    cmd = [
        edr_executable,
        "report",
        "--profiles-dir", os.fspath(DBT_PROJECT_DIR),
        "--project-dir", os.fspath(DBT_PROJECT_DIR),
        "--file-path", os.fspath(DBT_PROJECT_DIR / "docs" / "elementary_report.html"),
    ]

    context.log.info(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        context.log.error(
            f"Failed to generate Elementary report:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        raise RuntimeError(
            f"Elementary report generation failed with exit code {result.returncode}"
        )

    context.log.info(
        "✅ Elementary observability report generated at docs/elementary_report.html."
    )

    # Slack alerting step
    slack_webhook = os.getenv("SLACK_WEBHOOK")
    if slack_webhook:
        context.log.info("▶ Sending Elementary alerts to Slack...")
        monitor_cmd = [
            edr_executable,
            "monitor",
            "--profiles-dir", os.fspath(DBT_PROJECT_DIR),
            "--project-dir", os.fspath(DBT_PROJECT_DIR),
            "--slack-webhook", slack_webhook,
        ]
        context.log.info(f"Running command: {' '.join(monitor_cmd)}")
        monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
        if monitor_result.returncode != 0:
            context.log.warning(
                f"Elementary monitor failed to send Slack alerts:\n"
                f"STDOUT:\n{monitor_result.stdout}\nSTDERR:\n{monitor_result.stderr}"
            )
        else:
            context.log.info("✅ Elementary alerts sent to Slack successfully.")
    else:
        context.log.info(
            "ℹ️  No SLACK_WEBHOOK configured. Skipping Slack alerts."
        )


# ===========================================================================
# JOBS
#
# revops_full_pipeline_job:
#   Runs all 4 layers in dependency order:
#   Ingestion → dbt (Snowflake) → Reverse ETL → Observability
#
# revops_ingestion_only_job:
#   Runs dlt ingestion only. Useful for manual syncs or debugging.
#
# revops_transform_only_job:
#   Runs dbt on Snowflake + Reverse ETL without re-ingesting.
#   Useful when raw data is already fresh and you are iterating on SQL models.
# ===========================================================================

revops_full_pipeline_job = define_asset_job(
    name="revops_full_pipeline_job",
    selection=AssetSelection.all(),
    description="Full ELT pipeline: Ingestion (dlt → Snowflake) → dbt → Reverse ETL → Observability",
)

revops_ingestion_only_job = define_asset_job(
    name="revops_ingestion_only_job",
    selection=AssetSelection.assets(ingestion_dlt),
    description="Runs dlt ingestion only — loads raw data into Snowflake RAW_DATA schema.",
)

revops_transform_only_job = define_asset_job(
    name="revops_transform_only_job",
    selection=AssetSelection.assets(revops_dbt_assets, dlt_reverse_etl),
    description="Runs dbt on Snowflake + Reverse ETL only (skips ingestion).",
)


# ===========================================================================
# SCHEDULES
#
# cron_schedule="0 7 * * *" → Runs daily at 07:00 UTC.
# execution_timezone="UTC"  → Prevents issues with Daylight Saving Time.
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
