import os
import time
import json
import requests
import duckdb
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
DUCKDB_PATH = "./duckdb/revops_intelligence.duckdb"

# HubSpot API endpoints
HUBSPOT_BASE_URL = "https://api.hubapi.com"
SEARCH_URL = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/search"
UPDATE_URL = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/batch/update"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def get_hubspot_company_id_by_domain(domain):
    """Search for a HubSpot company by its domain."""
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "domain",
                        "operator": "EQ",
                        "value": domain
                    }
                ]
            }
        ],
        "properties": ["domain", "name"]
    }
    
    response = requests.post(SEARCH_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        results = response.json().get('results', [])
        if results:
            return results[0]['id']
    return None

def main():
    print("🚀 Starting RevOps Reverse ETL to HubSpot...")
    
    if not HUBSPOT_ACCESS_TOKEN or "xxxx" in HUBSPOT_ACCESS_TOKEN:
        print("⚠️ Warning: HUBSPOT_ACCESS_TOKEN is not set or is a placeholder in .env")
        print("⚠️ Running in DRY-RUN mode. No actual API calls will be made.\n")
        is_dry_run = True
    else:
        is_dry_run = False
        print("✅ HubSpot Access Token found. Running in LIVE mode.\n")

    try:
        # Connect to DuckDB
        conn = duckdb.connect(DUCKDB_PATH, read_only=True)
        
        # Query the data we want to sync
        # We only sync accounts that have a domain and some MRR or health status
        query = """
            SELECT 
                domain as canonical_domain,
                coalesce(hubspot_company_name, workspace_name) as account_name,
                mrr,
                health_status,
                CASE 
                    WHEN health_status = 'Healthy' THEN 100 
                    WHEN health_status = 'At Risk' THEN 50 
                    ELSE 0 
                END as health_score,
                is_pql,
                is_ready_for_upsell,
                is_payment_failing,
                seat_utilization_pct,
                last_activity_at
            FROM main_marts.dim_accounts
            WHERE domain IS NOT NULL
        """
        accounts_df = conn.execute(query).df()
        
        print(f"📊 Found {len(accounts_df)} accounts in DuckDB ready for sync.")
        
        updates = []
        synced_count = 0
        error_count = 0
        
        for index, row in accounts_df.iterrows():
            domain = row['canonical_domain']
            name = row['account_name']
            mrr = float(row['mrr']) if pd.notnull(row['mrr']) else 0.0
            health = row['health_status']
            score = int(row['health_score']) if pd.notnull(row['health_score']) else 0
            is_pql = bool(row['is_pql'])
            is_upsell = bool(row['is_ready_for_upsell'])
            is_payment_failing = bool(row['is_payment_failing'])
            seat_utilization = float(row['seat_utilization_pct']) if pd.notnull(row['seat_utilization_pct']) else 0.0
            last_activity = str(row['last_activity_at']) if pd.notnull(row['last_activity_at']) else ""
            
            print(f"🔄 Processing: {name} ({domain}) - Health: {health}, Score: {score}, PQL: {is_pql}")
            
            if is_dry_run:
                # Mock the sync process
                time.sleep(0.05)
                synced_count += 1
                continue
                
            # LIVE MODE: Search for company ID
            company_id = get_hubspot_company_id_by_domain(domain)
            
            if not company_id:
                print(f"   ❌ Could not find company in HubSpot with domain: {domain}")
                error_count += 1
                continue
                
            # Add to batch update list
            updates.append({
                "id": company_id,
                "properties": {
                    "stackflow_health_status": health,
                    "stackflow_health_score": str(score),
                    "current_mrr": str(mrr),
                    "is_product_qualified": "true" if is_pql else "false",
                    "ready_for_upsell": "true" if is_upsell else "false",
                    "payment_failing_signal": "true" if is_payment_failing else "false",
                    "seat_utilization_pct": str(seat_utilization),
                    "last_product_activity": last_activity
                }
            })
            
            # HubSpot batch limit is 100, let's sync in batches of 10
            if len(updates) >= 10:
                print(f"   📦 Pushing batch of 10 updates to HubSpot API...")
                batch_payload = {"inputs": updates}
                response = requests.post(UPDATE_URL, headers=HEADERS, json=batch_payload)
                
                if response.status_code in [200, 202, 207]:
                    synced_count += len(updates)
                else:
                    print(f"   ❌ Batch update failed: {response.text}")
                    error_count += len(updates)
                updates = []
                time.sleep(1) # Rate limit protection
                
        # Push remaining updates
        if updates and not is_dry_run:
            print(f"   📦 Pushing final batch of {len(updates)} updates to HubSpot API...")
            batch_payload = {"inputs": updates}
            response = requests.post(UPDATE_URL, headers=HEADERS, json=batch_payload)
            
            if response.status_code in [200, 202, 207]:
                synced_count += len(updates)
            else:
                print(f"   ❌ Batch update failed: {response.text}")
                error_count += len(updates)

        print("\n" + "="*50)
        print("✅ REVERSE ETL SYNC COMPLETE")
        print("="*50)
        print(f"Total processed: {len(accounts_df)}")
        print(f"Successfully synced: {synced_count}")
        print(f"Errors/Not Found: {error_count}")
        
        # Save a log file that Streamlit can read
        log_data = {
            "last_sync_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "status": "Success" if error_count == 0 else "Completed with errors",
            "total_processed": int(len(accounts_df)),
            "synced_count": int(synced_count),
            "error_count": int(error_count),
            "is_dry_run": is_dry_run
        }
        with open('./logs/latest_sync.json', 'w') as f:
            json.dump(log_data, f)
            
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        
if __name__ == "__main__":
    main()
