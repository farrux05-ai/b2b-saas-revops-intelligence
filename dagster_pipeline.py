import os
from dagster import asset, Definitions, AssetExecutionContext
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

@dbt_assets(manifest=DBT_PROJECT_DIR.joinpath("target", "manifest.json"))
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()

@asset(group_name="reverse_etl", deps=[revops_dbt_assets])
def hubspot_reverse_etl(context: AssetExecutionContext):
    """Sync insights back to HubSpot CRM."""
    context.log.info("Starting Reverse ETL to HubSpot...")
    os.system("python scripts/sync_to_hubspot.py")
    return "hubspot_sync_success"

defs = Definitions(
    assets=[ingestion_dlt, revops_dbt_assets, hubspot_reverse_etl],
    resources={
        "dbt": DbtCliResource(project_dir=os.fspath(DBT_PROJECT_DIR)),
    },
)
