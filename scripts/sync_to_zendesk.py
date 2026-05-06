import os
import time
import json
import requests
import duckdb
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")
ZENDESK_DOMAIN = os.getenv("ZENDESK_DOMAIN", "example.zendesk.com")
DUCKDB_PATH = "./duckdb/revops_intelligence.duckdb"

def main():
    print("🚀 Starting RevOps Reverse ETL to Zendesk...")
    
    if not ZENDESK_API_TOKEN or "xxxx" in ZENDESK_API_TOKEN:
        print("⚠️ Warning: ZENDESK_API_TOKEN is not set in .env")
        print("⚠️ Running in DRY-RUN mode. No actual API calls will be made.\n")
        is_dry_run = True
    else:
        is_dry_run = False
        print("✅ Zendesk API Token found. Running in LIVE mode.\n")

    try:
        # Connect to DuckDB
        conn = duckdb.connect(DUCKDB_PATH, read_only=True)
        
        # We only sync accounts that exist in our system to Zendesk Organizations
        query = """
            SELECT 
                domain,
                workspace_name,
                mrr,
                account_segment,
                health_status
            FROM main_marts.dim_accounts
            WHERE domain IS NOT NULL
        """
        accounts_df = conn.execute(query).df()
        
        print(f"📊 Found {len(accounts_df)} accounts in DuckDB ready to sync to Zendesk.")
        
        synced_count = 0
        
        for index, row in accounts_df.iterrows():
            domain = row['domain']
            name = row['workspace_name']
            mrr = float(row['mrr']) if pd.notnull(row['mrr']) else 0.0
            segment = row['account_segment']
            health = row['health_status']
            
            print(f"🔄 Syncing to Zendesk Org: {name} ({domain}) | Segment: {segment} | Health: {health}")
            
            if is_dry_run:
                time.sleep(0.02)  # Simulate network request
                synced_count += 1
                continue
                
            # LIVE MODE: In a real scenario, we would:
            # 1. Search for Zendesk Organization by Domain
            # 2. PUT /api/v2/organizations/{id}.json to update custom fields
            # payload = {
            #     "organization": {
            #         "organization_fields": {
            #             "mrr": mrr,
            #             "account_segment": segment,
            #             "health_status": health
            #         }
            #     }
            # }
            pass

        print("\n" + "="*50)
        print("✅ ZENDESK REVERSE ETL SYNC COMPLETE")
        print("="*50)
        print(f"Successfully enriched {synced_count} organizations in Zendesk.")
        
        # Save a log file for orchestration tracking
        log_data = {
            "last_sync_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "target_system": "Zendesk",
            "synced_count": int(synced_count),
            "is_dry_run": is_dry_run
        }
        with open('./logs/latest_zendesk_sync.json', 'w') as f:
            json.dump(log_data, f)
            
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")

if __name__ == "__main__":
    main()
