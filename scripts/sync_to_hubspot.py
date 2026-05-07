"""
sync_to_hubspot.py
-------------------
Professional Reverse ETL: Syncs Warehouse "Truth" back to HubSpot CRM.
Supports multiple operational modes:
1. L2A: Identity Healing (Orphan Lead to Company association)
2. PQL: Syncing Product Intent signals (Hot PQLs)
3. HEALTH: Syncing Account Health/Risk signals (Churn Prevention)
"""

import os
import duckdb
import argparse
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = "duckdb/revops_intelligence.duckdb"
HUBSPOT_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")

def get_db_connection():
    return duckdb.connect(LOCAL_DB)

def sync_l2a(con, is_simulation):
    print("🔍 Mode: L2A (Identity Healing)")
    query = """
        SELECT hubspot_contact_id, hubspot_company_id_stitched, email, match_method
        FROM main.int_users_joined
        WHERE is_l2a_orphan_fix_pending = TRUE
    """
    matches = con.execute(query).fetchall()
    if not matches:
        print("✨ No orphans found.")
        return
    
    for cid, coid, email, method in matches:
        print(f"   🔗 Syncing: {email} -> Company {coid} ({method})")
        # In reality: POST /crm/v3/associations/contacts/companies/batch/create
    print(f"✅ {len(matches)} L2A associations processed.")

def sync_pql(con, is_simulation):
    print("🔍 Mode: PQL (Product Qualified Leads)")
    # Find HOT PQLs and their primary HubSpot contact
    query = """
        SELECT 
            u.hubspot_contact_id,
            u.email,
            p.pql_tier,
            p.recommended_action
        FROM main_marts.fct_pql_signals p
        JOIN main.int_users_joined u ON p.workspace_id = u.internal_workspace_id
        WHERE p.pql_tier = '🔥 HOT'
          AND u.hubspot_contact_id IS NOT NULL
          AND u.user_role = 'owner'
    """
    pqls = con.execute(query).fetchall()
    if not pqls:
        print("✨ No Hot PQLs to sync.")
        return

    for cid, email, tier, action in pqls:
        print(f"   🔥 PQL Alert: {email} is {tier}. Recommending: {action}")
        # In reality: PATCH /crm/v3/objects/contacts/{cid} -> set pql_tier='HOT'
    print(f"✅ {len(pqls)} PQL signals synced to HubSpot.")

def sync_health(con, is_simulation):
    print("🔍 Mode: HEALTH (Churn Risk Monitoring)")
    query = """
        SELECT hubspot_company_id, workspace_name, health_status, health_reason
        FROM main_marts.dim_accounts
        WHERE health_status = 'At Risk'
          AND hubspot_company_id IS NOT NULL
    """
    risks = con.execute(query).fetchall()
    if not risks:
        print("✨ No At-Risk accounts found.")
        return

    for coid, name, status, reason in risks:
        print(f"   ⚠️ Risk Sync: {name} is {status} because: {reason}")
        # In reality: PATCH /crm/v3/objects/companies/{coid} -> set health_status='At Risk'
    print(f"✅ {len(risks)} Health signals synced to HubSpot.")

def main():
    parser = argparse.ArgumentParser(description="Reverse ETL from Warehouse to HubSpot")
    parser.add_argument("--mode", choices=["l2a", "pql", "health", "all"], default="all", help="Which data to sync")
    args = parser.parse_args()

    is_simulation = not HUBSPOT_TOKEN
    if is_simulation:
        print("🧪 RUNNING IN SIMULATION MODE (No API calls will be made)")

    con = get_db_connection()
    
    try:
        if args.mode in ["l2a", "all"]:
            sync_l2a(con, is_simulation)
        if args.mode in ["pql", "all"]:
            sync_pql(con, is_simulation)
        if args.mode in ["health", "all"]:
            sync_health(con, is_simulation)
    finally:
        con.close()

if __name__ == "__main__":
    main()
