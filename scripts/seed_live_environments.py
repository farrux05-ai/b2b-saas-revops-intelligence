"""
seed_live_environments.py
-------------------------
A utility script to populate actual HubSpot (test account) and Zendesk (trial account)
using the local mock data stored in JSON files.

This enables you to show a REAL data flow in your portfolio video:
1. Seed raw data into HubSpot and Zendesk APIs.
2. Ingest it via dlt/Dagster (requires changing dlt pipelines to use actual APIs).
3. Run transformations.
4. Push enriched health/MRR/PQL metrics back using Reverse ETL!

Usage:
  1. Set environment variables in .env:
     HUBSPOT_ACCESS_TOKEN=your_token
     ZENDESK_SUBDOMAIN=your_subdomain
     ZENDESK_EMAIL=your_email
     ZENDESK_API_TOKEN=your_api_token
  2. Run: python scripts/seed_live_environments.py
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

# API Configuration
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN", "")
ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL", "")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN", "")

# Limits for seeding (reduces API call overhead, 15 records is plenty for a beautiful UI demo)
SEED_LIMIT = 15

# HubSpot API endpoints
HS_HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def seed_hubspot():
    if not HUBSPOT_ACCESS_TOKEN or HUBSPOT_ACCESS_TOKEN == "mock_token":
        print("⏭️  Skipping HubSpot seeding: HUBSPOT_ACCESS_TOKEN is missing or mock.")
        return {}

    print("\n🚀 Starting HubSpot seeding (First 15 records)...")
    
    # 1. Load data
    with open("data/raw/hubspot_companies.json", "r") as f:
        companies = json.load(f)[:SEED_LIMIT]
    with open("data/raw/hubspot_contacts.json", "r") as f:
        contacts = json.load(f)
    with open("data/raw/hubspot_deals.json", "r") as f:
        deals = json.load(f)

    # 2. Seed Companies and map: mock_id -> real_hubspot_id
    company_mappings = {}
    print(f"🏢 Seeding {len(companies)} companies to HubSpot...")
    for co in companies:
        payload = {
            "properties": {
                "name": co["name"],
                "domain": co["domain"],
                "industry": co["industry"],
                "lifecyclestage": co["lifecyclestage"],
                "hs_lead_status": co["hs_lead_status"]
            }
        }
        res = requests.post("https://api.hubapi.com/crm/v3/objects/companies", headers=HS_HEADERS, json=payload)
        if res.status_code == 201:
            real_id = res.json()["id"]
            company_mappings[co["hs_object_id"]] = real_id
            print(f"  ✅ Created Company: {co['name']} (ID: {real_id})")
        else:
            print(f"  ❌ Failed to create Company {co['name']}: {res.text}")
        time.sleep(0.1)  # Respect rate limit

    # 3. Seed Contacts (and associate with real Company IDs)
    seeded_contact_count = 0
    print(f"\n👤 Seeding contacts for seeded companies...")
    for ct in contacts:
        # Only seed contacts that belong to a company we actually seeded
        mock_co_id = ct.get("associated_company_id")
        if not mock_co_id or mock_co_id not in company_mappings:
            continue
        
        real_co_id = company_mappings[mock_co_id]
        payload = {
            "properties": {
                "email": ct["email"],
                "firstname": ct["firstname"],
                "lastname": ct["lastname"],
                "jobtitle": ct["jobtitle"]
            },
            "associations": [
                {
                    "to": {"id": real_co_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 1 # Contact to Company
                        }
                    ]
                }
            ]
        }
        res = requests.post("https://api.hubapi.com/crm/v3/objects/contacts", headers=HS_HEADERS, json=payload)
        if res.status_code == 201:
            real_id = res.json()["id"]
            print(f"  ✅ Created Contact: {ct['email']} (Real ID: {real_id}) associated with Company ID {real_co_id}")
            seeded_contact_count += 1
        else:
            print(f"  ❌ Failed to create Contact {ct['email']}: {res.text}")
        time.sleep(0.1)
        if seeded_contact_count >= SEED_LIMIT:
            break

    # 4. Seed Deals (and associate with real Company IDs)
    seeded_deal_count = 0
    print(f"\n💸 Seeding deals for seeded companies...")
    for dl in deals:
        mock_co_id = dl.get("associated_company_id")
        if not mock_co_id or mock_co_id not in company_mappings:
            continue
        
        real_co_id = company_mappings[mock_co_id]
        
        # Format closedate to ISO8601 if present
        close_date = dl.get("closedate")
        
        # HubSpot requires stage in lower case or standard pipeline stage codes (e.g. closedwon)
        stage = dl["dealstage"]
        if stage == "closedwon":
            stage = "closedwon"
        elif stage == "closedlost":
            stage = "closedlost"
        else:
            stage = "appointmentscheduled" # Fallback to default first stage
            
        payload = {
            "properties": {
                "dealname": dl["dealname"],
                "dealstage": stage,
                "amount": str(dl["amount"]),
                "pipeline": "default",
                "closedate": close_date
            },
            "associations": [
                {
                    "to": {"id": real_co_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 5 # Deal to Company
                        }
                    ]
                }
            ]
        }
        res = requests.post("https://api.hubapi.com/crm/v3/objects/deals", headers=HS_HEADERS, json=payload)
        if res.status_code == 201:
            real_id = res.json()["id"]
            print(f"  ✅ Created Deal: {dl['dealname']} (Real ID: {real_id}) associated with Company ID {real_co_id}")
            seeded_deal_count += 1
        else:
            print(f"  ❌ Failed to create Deal {dl['dealname']}: {res.text}")
        time.sleep(0.1)
        if seeded_deal_count >= SEED_LIMIT:
            break
            
    print("🎉 HubSpot seeding complete.")
    return company_mappings


def seed_zendesk():
    if not ZENDESK_SUBDOMAIN or not ZENDESK_API_TOKEN or ZENDESK_API_TOKEN == "mock_token":
        print("⏭️  Skipping Zendesk seeding: credentials are missing or mock.")
        return

    print("\n🚀 Starting Zendesk seeding...")
    
    # Load zendesk ticket data
    with open("data/raw/zendesk_tickets.json", "r") as f:
        tickets = json.load(f)[:SEED_LIMIT]

    # Zendesk authentication (requires email + /token appended to username)
    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json"

    print(f"Ticket count to seed: {len(tickets)}")
    for tk in tickets:
        # Map raw status & priority (ensuring compatibility)
        status = tk["ticket_status"]
        if status not in ["new", "open", "pending", "hold", "solved", "closed"]:
            status = "new"
            
        priority = tk["priority"]
        if priority not in ["low", "normal", "high", "urgent"]:
            priority = "normal"

        payload = {
            "ticket": {
                "subject": tk["subject"],
                "comment": {
                    "body": f"System generated ticket for {tk.get('requester_email')}. Created for local dbt/Dagster pipeline tests."
                },
                "requester": {
                    "name": tk.get("requester_email", "Requester").split("@")[0].capitalize(),
                    "email": tk.get("requester_email")
                },
                "status": status,
                "priority": priority
            }
        }
        
        res = requests.post(url, auth=auth, json=payload)
        if res.status_code == 201:
            ticket_id = res.json()["ticket"]["id"]
            print(f"  ✅ Created Zendesk Ticket #{ticket_id}: \"{tk['subject']}\" for {tk['requester_email']}")
        else:
            print(f"  ❌ Failed to create Ticket \"{tk['subject']}\": {res.text}")
        time.sleep(0.2) # Avoid hitting Zendesk rate limits (normally 100/min)

    print("🎉 Zendesk seeding complete.")


if __name__ == "__main__":
    print("🌟 GTM Seeding Utility started.")
    company_maps = seed_hubspot()
    seed_zendesk()
    print("\n✨ Seeding process finished. You can now configure your pipeline to read/write real data.")
