import os
from dagster import asset, Definitions, AssetExecutionContext, ScheduleDefinition, define_asset_job, AssetKey
from dagster_dbt import DbtCliResource, dbt_assets
from pathlib import Path

# Paths
DBT_PROJECT_DIR = Path(__file__).parent.joinpath("").resolve()

@asset(group_name="ingestion")
def ingestion_dlt(context: AssetExecutionContext):
    """Run the dlt ingestion pipeline."""
    context.log.info("Starting dlt ingestion...")
    # Trigger the dlt script
    os.system("python ingestion/stackflow_pipeline.py")
    return "dlt_success"

@dbt_assets(
    manifest=DBT_PROJECT_DIR.joinpath("target", "manifest.json"),
    deps=[AssetKey("ingestion_dlt")]
)
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()

@asset(group_name="sync", deps=[revops_dbt_assets])
def motherduck_sync(context: AssetExecutionContext):
    """Sync local DuckDB data to MotherDuck."""
    context.log.info("Starting sync to MotherDuck...")
    os.system("python scripts/sync_to_motherduck.py")
    return "motherduck_sync_success"

@asset(group_name="reverse_etl", deps=[motherduck_sync])
def hubspot_reverse_etl(context: AssetExecutionContext):
    """Sync insights back to HubSpot CRM."""
    context.log.info("Starting Reverse ETL to HubSpot...")
    os.system("python scripts/sync_to_hubspot.py")
    return "hubspot_sync_success"

@asset(group_name="reverse_etl", deps=[motherduck_sync])
def zendesk_reverse_etl(context: AssetExecutionContext):
    """Sync insights back to Zendesk Support."""
    context.log.info("Starting Reverse ETL to Zendesk...")
    os.system("python scripts/sync_to_zendesk.py")
    return "zendesk_sync_success"

# Define a daily job and schedule
revops_daily_job = define_asset_job("revops_daily_job", selection="*")
revops_daily_schedule = ScheduleDefinition(
    job=revops_daily_job,
    cron_schedule="0 7 * * *", # Run at 07:00 UTC every day
    execution_timezone="UTC",
)

defs = Definitions(
    assets=[ingestion_dlt, revops_dbt_assets, motherduck_sync, hubspot_reverse_etl, zendesk_reverse_etl],
    schedules=[revops_daily_schedule],
    resources={
        "dbt": DbtCliResource(project_dir=os.fspath(DBT_PROJECT_DIR)),
    },
)
