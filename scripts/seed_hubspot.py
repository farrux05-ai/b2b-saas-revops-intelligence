import os
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
HUBSPOT_BASE_URL = "https://api.hubapi.com/crm/v3/objects/companies"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def get_companies_from_postgres():
    """Fetch company names and domains from local Postgres."""
    print("🐘 Connecting to local Postgres database...")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # Using 'raw.hubspot_companies' as the source for seeding HubSpot
        query = "SELECT name, domain FROM raw.hubspot_companies WHERE domain IS NOT NULL LIMIT 50"
        cur.execute(query)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Postgres Error: {e}")
        return []

def create_hubspot_company(name, domain):
    """Create a company in HubSpot."""
    payload = {
        "properties": {
            "name": name,
            "domain": domain
        }
    }
    
    response = requests.post(HUBSPOT_BASE_URL, headers=HEADERS, json=payload)
    
    if response.status_code == 201:
        print(f"✅ Successfully created: {name} ({domain})")
        return True
    elif response.status_code == 409:
        print(f"ℹ️ Already exists: {name} ({domain})")
        return False
    else:
        print(f"❌ Error creating {name}: {response.text}")
        return False

def main():
    print("🚀 Starting HubSpot Seeding Process...")
    
    if not HUBSPOT_ACCESS_TOKEN or "xxxx" in HUBSPOT_ACCESS_TOKEN:
        print("❌ Error: Valid HUBSPOT_ACCESS_TOKEN not found in .env")
        return

    # 1. Get data from Postgres
    companies = get_companies_from_postgres()
    
    if not companies:
        print("⚠️ No companies found in Postgres to seed.")
        return
    
    print(f"📊 Found {len(companies)} companies. Starting HubSpot upload...")

    # 2. Upload to HubSpot
    created_count = 0
    for co in companies:
        name = co['name']
        domain = co['domain']
        
        if create_hubspot_company(name, domain):
            created_count += 1
        
        # Avoid rate limits
        time.sleep(0.5)

    print("\n" + "="*40)
    print(f"🎉 Seeding Complete!")
    print(f"Total processed: {len(companies)}")
    print(f"New companies created: {created_count}")
    print("="*40)

if __name__ == "__main__":
    main()
