import argparse
import duckdb
import os
import sys

# Ensure the root of the project is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from scripts.reverse_etl.destinations.hubspot import HubSpotConnector
from scripts.reverse_etl.destinations.zendesk import ZendeskConnector
from scripts.reverse_etl.destinations.facebook_custom_audiences import FacebookAdsConnector
from scripts.reverse_etl.destinations.quickbooks import QuickBooksConnector

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'duckdb', 'revops_intelligence.duckdb')
    return duckdb.connect(db_path)

def main():
    parser = argparse.ArgumentParser(description="Modular Reverse ETL Framework")
    parser.add_argument(
        '--destination', 
        choices=['hubspot', 'zendesk', 'facebook', 'quickbooks', 'all'],
        required=True,
        help="Target destination for Reverse ETL"
    )
    parser.add_argument(
        '--mode', 
        choices=['l2a', 'pql', 'health', 'all'],
        default='all',
        help="Specific sync mode (mostly used for HubSpot)"
    )
    parser.add_argument(
        '--live', 
        action='store_true',
        help="Run in LIVE mode (actually send data to APIs). Default is Simulation."
    )
    
    args = parser.parse_args()
    is_simulation = not args.live
    
    con = get_db_connection()
    
    print("\n" + "="*50)
    print(f"🚀 REVERSE ETL FRAMEWORK (Simulation: {is_simulation})")
    print("="*50 + "\n")

    if args.destination in ['hubspot', 'all']:
        connector = HubSpotConnector(is_simulation=is_simulation)
        connector.sync(con, mode=args.mode)
        print("-" * 30)

    if args.destination in ['zendesk', 'all']:
        connector = ZendeskConnector(is_simulation=is_simulation)
        connector.sync(con)
        print("-" * 30)
        
    if args.destination in ['facebook', 'all']:
        connector = FacebookAdsConnector(is_simulation=is_simulation)
        connector.sync(con)
        print("-" * 30)
        
    if args.destination in ['quickbooks', 'all']:
        connector = QuickBooksConnector(is_simulation=is_simulation)
        connector.sync(con)
        print("-" * 30)

    print("\n✅ All specified syncs completed.\n")

if __name__ == "__main__":
    main()
