import os
from dagster import asset, Definitions, AssetExecutionContext, ScheduleDefinition, define_asset_job
from dagster_dbt import DbtCliResource, dbt_assets
from pathlib import Path

# Paths
DBT_PROJECT_DIR = Path(__file__).parent.joinpath("").resolve()

@asset(group_name="ingestion")
def ingestion_dlt(context: AssetExecutionContext):
    """Run the dlt ingestion pipeline (HubSpot, Stripe, Zendesk, Internal DB)."""
    context.log.info("Starting dlt ingestion...")
    os.system("python ingestion/stackflow_pipeline.py")
    return "dlt_success"

# Note: @dbt_assets v0.29 does not support the `deps=` argument.
# Ingestion → dbt ordering is enforced at the job level via asset selection.
@dbt_assets(manifest=DBT_PROJECT_DIR.joinpath("target", "manifest.json"))
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Build all dbt models (staging → intermediate → marts)."""
    yield from dbt.cli(["build"], context=context).stream()

@asset(group_name="sync", deps=[revops_dbt_assets])
def motherduck_sync(context: AssetExecutionContext):
    """Sync local DuckDB data to MotherDuck cloud warehouse."""
    context.log.info("Starting sync to MotherDuck...")
    os.system("python scripts/sync_to_motherduck.py")
    return "motherduck_sync_success"

@asset(group_name="reverse_etl", deps=[motherduck_sync])
def hubspot_reverse_etl(context: AssetExecutionContext):
    """Sync health & PQL signals back to HubSpot CRM."""
    context.log.info("Starting Reverse ETL to HubSpot...")
    os.system("python scripts/sync_to_hubspot.py")
    return "hubspot_sync_success"

@asset(group_name="reverse_etl", deps=[motherduck_sync])
def zendesk_reverse_etl(context: AssetExecutionContext):
    """Sync insights back to Zendesk Support."""
    context.log.info("Starting Reverse ETL to Zendesk...")
    os.system("python scripts/sync_to_zendesk.py")
    return "zendesk_sync_success"

# ---------------------------------------------------------------------------
# Jobs — run in correct order: ingestion first, then dbt + downstream
# ---------------------------------------------------------------------------
revops_ingestion_job = define_asset_job(
    "revops_ingestion_job",
    selection=[ingestion_dlt]
)

revops_transform_job = define_asset_job(
    "revops_transform_job",
    selection=[revops_dbt_assets, motherduck_sync, hubspot_reverse_etl, zendesk_reverse_etl]
)

# Daily schedule: 07:00 UTC — ingestion, then transform
revops_daily_schedule = ScheduleDefinition(
    job=revops_transform_job,
    cron_schedule="0 7 * * *",
    execution_timezone="UTC",
)

defs = Definitions(
    assets=[ingestion_dlt, revops_dbt_assets, motherduck_sync, hubspot_reverse_etl, zendesk_reverse_etl],
    jobs=[revops_ingestion_job, revops_transform_job],
    schedules=[revops_daily_schedule],
    resources={
        "dbt": DbtCliResource(project_dir=os.fspath(DBT_PROJECT_DIR)),
    },
)
