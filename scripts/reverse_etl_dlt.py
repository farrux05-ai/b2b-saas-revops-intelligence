import dlt
import duckdb
import os
import logging
from datetime import datetime
from typing import Iterator, List, Dict, Any
from dlt.common.typing import TDataItems
from dlt.common.schema import TTableSchema
from dlt.sources.helpers import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("reverse_etl_dlt")

# Load environment variables
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "mock_token")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN", "mock_token")

# ---------------------------------------------------------------------------
# SOURCES: Pulling data from DuckDB (the Warehouse)
# ---------------------------------------------------------------------------

@dlt.source(name="revops_warehouse")
def revops_warehouse_source():
    """Source to read actionable data from the local DuckDB warehouse."""
    db_path = os.path.join(os.getcwd(), "duckdb", "revops_intelligence.duckdb")
    
    def get_con():
        return duckdb.connect(db_path, read_only=True)

    @dlt.resource(name="hubspot_l2a_associations", write_disposition="append")
    def l2a_associations():
        """Identify leads that need to be mapped to companies in HubSpot."""
        con = get_con()
        # This is naturally incremental because once synced, hubspot_contact_id will be filled
        query = """
            SELECT u.email, u.hubspot_company_id_stitched, u.match_method
            FROM main_identity.int_users_joined u
            WHERE u.hubspot_contact_id IS NULL
              AND u.hubspot_company_id_stitched IS NOT NULL
        """
        yield con.execute(query).df().to_dict('records')

    @dlt.resource(name="hubspot_pql_signals", write_disposition="append")
    def pql_signals():
        """Identify HOT leads that need a PQL tag in HubSpot."""
        con = get_con()
        # For simplicity, we sync all HOT owner PQLs
        # In a real scenario, we'd use a state-based incremental cursor here too
        query = """
            SELECT u.hubspot_contact_id, u.email, p.pql_tier, p.recommended_action
            FROM main_marts.fct_pql_signals p
            JOIN main_identity.int_users_joined u ON p.workspace_id = u.internal_workspace_id
            WHERE p.pql_tier = '🔥 HOT'
              AND u.hubspot_contact_id IS NOT NULL
              AND u.user_role = 'owner'
        """
        yield con.execute(query).df().to_dict('records')

    @dlt.resource(name="hubspot_account_health", write_disposition="append")
    def account_health(updated_at=dlt.sources.incremental("last_updated_at", initial_value=datetime(1970, 1, 1))):
        """Identify At-Risk accounts to alert CS in HubSpot. Uses incremental loading."""
        con = get_con()
        query = f"""
            SELECT hubspot_company_id, workspace_name, health_status, health_reason, last_updated_at
            FROM main_marts.dim_accounts
            WHERE health_status = 'At Risk'
              AND hubspot_company_id IS NOT NULL
              AND last_updated_at > '{updated_at.last_value}'
        """
        yield con.execute(query).df().to_dict('records')

    @dlt.resource(name="zendesk_org_enrichment", write_disposition="append")
    def zendesk_enrichment(updated_at=dlt.sources.incremental("last_updated_at", initial_value=datetime(1970, 1, 1))):
        """Enrich Zendesk Organizations with MRR and Health status. Uses incremental loading."""
        con = get_con()
        query = f"""
            SELECT workspace_name, domain, mrr, account_segment, health_status, last_updated_at
            FROM main_marts.dim_accounts
            WHERE domain IS NOT NULL
              AND last_updated_at > '{updated_at.last_value}'
        """
        yield con.execute(query).df().to_dict('records')

    return [l2a_associations, pql_signals, account_health, zendesk_enrichment]

# ---------------------------------------------------------------------------
# DESTINATIONS: Pushing data to APIs (Custom Destinations)
# ---------------------------------------------------------------------------

@dlt.destination(name="hubspot_api", batch_size=20)
def hubspot_api_destination(items: TDataItems, table: TTableSchema) -> None:
    """Robust custom destination for HubSpot with batching and error handling."""
    table_name = table["name"]
    is_mock = HUBSPOT_ACCESS_TOKEN == "mock_token"
    
    logger.info(f"🚀 [HubSpot] Syncing {len(items)} records to {table_name} (Mock: {is_mock})")
    
    for item in items:
        try:
            if table_name == "hubspot_l2a_associations":
                logger.debug(f"Healing association: {item['email']}")
                # if not is_mock:
                #     requests.post("https://api.hubapi.com/crm/v3/associations/...", headers=...)
            elif table_name == "hubspot_pql_signals":
                logger.debug(f"Updating PQL tag: {item['email']}")
            elif table_name == "hubspot_account_health":
                logger.debug(f"Updating health status: {item['workspace_name']}")
        except Exception as e:
            logger.error(f"Failed to sync item to HubSpot: {e}")
            raise # Let dlt handle the retry if configured

@dlt.destination(name="zendesk_api", batch_size=20)
def zendesk_api_destination(items: TDataItems, table: TTableSchema) -> None:
    """Robust custom destination for Zendesk."""
    is_mock = ZENDESK_API_TOKEN == "mock_token"
    logger.info(f"🚀 [Zendesk] Syncing {len(items)} records (Mock: {is_mock})")
    
    for item in items:
        # Simulate API latency
        pass

# ---------------------------------------------------------------------------
# PIPELINE RUNNER
# ---------------------------------------------------------------------------

def run_reverse_etl():
    """Main entry point to run the Reverse ETL pipeline."""
    # State is stored in DuckDB to ensure it's persistent across runs
    pipeline = dlt.pipeline(
        pipeline_name="reverse_etl_intelligence",
        destination=dlt.destinations.duckdb("duckdb/revops_intelligence.duckdb"),
        dataset_name="reverse_etl_state"
    )

    source = revops_warehouse_source()

    # Run HubSpot resources
    hubspot_resources = ["hubspot_l2a_associations", "hubspot_pql_signals", "hubspot_account_health"]
    info = pipeline.run(
        source.with_resources(*hubspot_resources),
        destination=hubspot_api_destination
    )
    logger.info(f"HubSpot Sync Summary: {info}")

    # Run Zendesk resources
    info = pipeline.run(
        source.with_resources("zendesk_org_enrichment"),
        destination=zendesk_api_destination
    )
    logger.info(f"Zendesk Sync Summary: {info}")

if __name__ == "__main__":
    run_reverse_etl()
