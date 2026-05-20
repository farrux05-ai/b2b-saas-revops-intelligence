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

# HubSpot API Headers
HS_HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# ---------------------------------------------------------------------------
# SOURCES: Pulling data from DuckDB (the Warehouse)
# ---------------------------------------------------------------------------

@dlt.source(name="revops_warehouse")
def revops_warehouse_source():
    """Source to read actionable data from the local DuckDB warehouse."""
    db_path = os.path.join(os.getcwd(), "duckdb", "revops_intelligence.duckdb")
    
    def get_con():
        return duckdb.connect(db_path, read_only=True)

    @dlt.resource(name="hubspot_l2a_associations", write_disposition="merge", primary_key="email")
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

    @dlt.resource(name="hubspot_pql_signals", write_disposition="merge", primary_key="email")
    def pql_signals():
        """Identify HOT leads that need a PQL tag in HubSpot."""
        con = get_con()
        # For simplicity, we sync all HOT owner PQLs
        # In a real scenario, we'd use a state-based incremental cursor here too
        query = """
            SELECT u.hubspot_contact_id, u.email, p.intent_tier, p.recommended_action
            FROM main_marts.fct_pql_signals p
            JOIN main_identity.int_users_joined u ON p.workspace_id = u.internal_workspace_id
            WHERE p.intent_tier = 'HOT'
              AND u.hubspot_contact_id IS NOT NULL
              AND u.user_role = 'owner'
        """
        yield con.execute(query).df().to_dict('records')

    @dlt.resource(name="hubspot_company_enrichment", write_disposition="merge", primary_key="hubspot_company_id")
    def company_enrichment(updated_at=dlt.sources.incremental("last_updated_at", initial_value=datetime(1970, 1, 1))):
        """Enrich HubSpot Companies with health metrics and MRR. Uses incremental loading."""
        con = get_con()
        query = f"""
            SELECT hubspot_company_id, workspace_name, health_status, health_reason, mrr, account_segment, last_updated_at
            FROM main_marts.dim_accounts
            WHERE hubspot_company_id IS NOT NULL
              AND last_updated_at > '{updated_at.last_value}'
        """
        yield con.execute(query).df().to_dict('records')

    return [l2a_associations, pql_signals, company_enrichment]

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
                if not is_mock:
                    # 1. Search for contact by email to get their HubSpot contact ID
                    search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
                    search_payload = {
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "email",
                                        "operator": "EQ",
                                        "value": item["email"]
                                    }
                                ]
                            }
                        ]
                    }
                    res = requests.post(search_url, headers=HS_HEADERS, json=search_payload)
                    contact_id = None
                    if res.status_code == 200:
                        results = res.json().get("results", [])
                        if results:
                            contact_id = results[0]["id"]
                    
                    # 2. If contact not found, create them
                    if not contact_id:
                        create_url = "https://api.hubapi.com/crm/v3/objects/contacts"
                        create_payload = {
                            "properties": {
                                "email": item["email"]
                            }
                        }
                        res = requests.post(create_url, headers=HS_HEADERS, json=create_payload)
                        if res.status_code == 201:
                            contact_id = res.json()["id"]
                    
                    # 3. Associate contact with company
                    if contact_id:
                        assoc_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/companies/{item['hubspot_company_id_stitched']}/1"
                        res = requests.put(assoc_url, headers=HS_HEADERS)
                        if res.status_code in [200, 204]:
                            logger.info(f"  ✅ Associated Contact {item['email']} with Company {item['hubspot_company_id_stitched']}")
                        else:
                            logger.warning(f"  ⚠️ Association failed: {res.text}")
                    else:
                        logger.warning(f"  ⚠️ Could not resolve Contact for {item['email']}")
            
            elif table_name == "hubspot_pql_signals":
                logger.debug(f"Updating PQL tag: {item['email']}")
                if not is_mock:
                    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{item['hubspot_contact_id']}"
                    payload = {
                        "properties": {
                            "intent_tier": item["intent_tier"],
                            "recommended_action": item["recommended_action"]
                        }
                    }
                    res = requests.patch(url, headers=HS_HEADERS, json=payload)
                    if res.status_code == 200:
                        logger.info(f"  ✅ Updated PQL status for contact {item['email']} in HubSpot.")
                    else:
                        logger.warning(f"  ⚠️ HubSpot Contact Update Warning: {res.text}")
            
            elif table_name == "hubspot_company_enrichment":
                logger.debug(f"Updating company health/MRR: {item['workspace_name']}")
                if not is_mock:
                    url = f"https://api.hubapi.com/crm/v3/objects/companies/{item['hubspot_company_id']}"
                    payload = {
                        "properties": {
                            "health_status": item["health_status"],
                            "health_reason": item["health_reason"],
                            "mrr": str(item["mrr"]) if item.get("mrr") is not None else "0",
                            "account_segment": item["account_segment"]
                        }
                    }
                    res = requests.patch(url, headers=HS_HEADERS, json=payload)
                    if res.status_code == 200:
                        logger.info(f"  ✅ Updated Company {item['workspace_name']} in HubSpot.")
                    else:
                        logger.warning(f"  ⚠️ HubSpot Company Update Warning: {res.text}")
        except Exception as e:
            logger.error(f"Failed to sync item to HubSpot: {e}")
            raise # Let dlt handle the retry if configured

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
    hubspot_resources = ["hubspot_l2a_associations", "hubspot_pql_signals", "hubspot_company_enrichment"]
    info = pipeline.run(
        source.with_resources(*hubspot_resources),
        destination=hubspot_api_destination
    )
    logger.info(f"HubSpot Sync Summary: {info}")

if __name__ == "__main__":
    run_reverse_etl()
