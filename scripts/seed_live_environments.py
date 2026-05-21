"""
seed_live_environments.py
-------------------------
Populates actual HubSpot (using API) with local mock data,
and updates the local JSON files with the generated real HubSpot IDs.

This ensures that:
  1. The raw data contains actual HubSpot object IDs.
  2. The dlt ingestion loads real HubSpot IDs into DuckDB.
  3. Downstream dbt models and reverse ETL work flawlessly with actual CRM records.

Usage:
  python scripts/seed_live_environments.py
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN", "")
ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL", "")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN", "")

HS_HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

ALLOWED_INDUSTRIES = [
    "ACCOUNTING", "AIRLINES_AVIATION", "ALTERNATIVE_DISPUTE_RESOLUTION", "ALTERNATIVE_MEDICINE", "ANIMATION", 
    "APPAREL_FASHION", "ARCHITECTURE_PLANNING", "ARTS_AND_CRAFTS", "AUTOMOTIVE", "AVIATION_AEROSPACE", "BANKING", 
    "BIOTECHNOLOGY", "BROADCAST_MEDIA", "BUILDING_MATERIALS", "BUSINESS_SUPPLIES_AND_EQUIPMENT", "CAPITAL_MARKETS", 
    "CHEMICALS", "CIVIC_SOCIAL_ORGANIZATION", "CIVIL_ENGINEERING", "COMMERCIAL_REAL_ESTATE", "COMPUTER_NETWORK_SECURITY", 
    "COMPUTER_GAMES", "COMPUTER_HARDWARE", "COMPUTER_NETWORKING", "COMPUTER_SOFTWARE", "INTERNET", "CONSTRUCTION", 
    "CONSUMER_ELECTRONICS", "CONSUMER_GOODS", "CONSUMER_SERVICES", "COSMETICS", "DAIRY", "DEFENSE_SPACE", "DESIGN", 
    "EDUCATION_MANAGEMENT", "E_LEARNING", "ELECTRICAL_ELECTRONIC_MANUFACTURING", "ENTERTAINMENT", "ENVIRONMENTAL_SERVICES", 
    "EVENTS_SERVICES", "EXECUTIVE_OFFICE", "FACILITIES_SERVICES", "FARMING", "FINANCIAL_SERVICES", "FINE_ART", "FISHERY", 
    "FOOD_BEVERAGES", "FOOD_PRODUCTION", "FUND_RAISING", "FURNITURE", "GAMBLING_CASINOS", "GLASS_CERAMICS_CONCRETE", 
    "GOVERNMENT_ADMINISTRATION", "GOVERNMENT_RELATIONS", "GRAPHIC_DESIGN", "HEALTH_WELLNESS_AND_FITNESS", "HIGHER_EDUCATION", 
    "HOSPITAL_HEALTH_CARE", "HOSPITALITY", "HUMAN_RESOURCES", "IMPORT_AND_EXPORT", "INDIVIDUAL_FAMILY_SERVICES", 
    "INDUSTRIAL_AUTOMATION", "INFORMATION_SERVICES", "INFORMATION_TECHNOLOGY_AND_SERVICES", "INSURANCE", "INTERNATIONAL_AFFAIRS", 
    "INTERNATIONAL_TRADE_AND_DEVELOPMENT", "INVESTMENT_BANKING", "INVESTMENT_MANAGEMENT", "JUDICIARY", "LAW_ENFORCEMENT", 
    "LAW_PRACTICE", "LEGAL_SERVICES", "LEGISLATIVE_OFFICE", "LEISURE_TRAVEL_TOURISM", "LIBRARIES", "LOGISTICS_AND_SUPPLY_CHAIN", 
    "LUXURY_GOODS_JEWELRY", "MACHINERY", "MANAGEMENT_CONSULTING", "MARITIME", "MARKET_RESEARCH", "MARKETING_AND_ADVERTISING", 
    "MECHANICAL_OR_INDUSTRIAL_ENGINEERING", "MEDIA_PRODUCTION", "MEDICAL_DEVICES", "MEDICAL_PRACTICE", "MENTAL_HEALTH_CARE", 
    "MILITARY", "MINING_METALS", "MOTION_PICTURES_AND_FILM", "MUSEUMS_AND_INSTITUTIONS", "MUSIC", "NANOTECHNOLOGY", 
    "NEWSPAPERS", "NON_PROFIT_ORGANIZATION_MANAGEMENT", "OIL_ENERGY", "ONLINE_MEDIA", "OUTSOURCING_OFFSHORING", 
    "PACKAGE_FREIGHT_DELIVERY", "PACKAGING_AND_CONTAINERS", "PAPER_FOREST_PRODUCTS", "PERFORMING_ARTS", "PHARMACEUTICALS", 
    "PHILANTHROPY", "PHOTOGRAPHY", "PLASTICS", "POLITICAL_ORGANIZATION", "PRIMARY_SECONDARY_EDUCATION", "PRINTING", 
    "PROFESSIONAL_TRAINING_COACHING", "PROGRAM_DEVELOPMENT", "PUBLIC_POLICY", "PUBLIC_RELATIONS_AND_COMMUNICATIONS", 
    "PUBLIC_SAFETY", "PUBLISHING", "RAILROAD_MANUFACTURE", "RANCHING", "REAL_ESTATE", "RECREATIONAL_FACILITIES_AND_SERVICES", 
    "RELIGIOUS_INSTITUTIONS", "RENEWABLES_ENVIRONMENT", "RESEARCH", "RESTAURANTS", "RETAIL", "SECURITY_AND_INVESTIGATIONS", 
    "SEMICONDUCTORS", "SHIPBUILDING", "SPORTING_GOODS", "SPORTS", "STAFFING_AND_RECRUITING", "SUPERMARKETS", 
    "TELECOMMUNICATIONS", "TEXTILES", "THINK_TANKS", "TOBACCO", "TRANSLATION_AND_LOCALIZATION", "TRANSPORTATION_TRUCKING_RAILROAD", 
    "UTILITIES", "VENTURE_CAPITAL_PRIVATE_EQUITY", "VETERINARY", "WAREHOUSING", "WHOLESALE", "WINE_AND_SPIRITS", "WIRELESS", 
    "WRITING_AND_EDITING", "MOBILE_GAMES"
]

def seed_hubspot():
    if not HUBSPOT_ACCESS_TOKEN or HUBSPOT_ACCESS_TOKEN == "mock_token":
        print("⏭️  Skipping HubSpot seeding: HUBSPOT_ACCESS_TOKEN is missing or mock.")
        return

    print("\n🚀 Starting HubSpot seeding for ALL local mock data...")
    
    # 1. Load data
    with open("data/raw/hubspot_companies.json", "r") as f:
        companies = json.load(f)
    with open("data/raw/hubspot_contacts.json", "r") as f:
        contacts = json.load(f)
    with open("data/raw/hubspot_deals.json", "r") as f:
        deals = json.load(f)

    # 2. Seed Companies and map: mock_id -> real_hubspot_id
    company_mappings = {}
    print(f"🏢 Seeding {len(companies)} companies to HubSpot...")
    for co in companies:
        industry = co.get("industry", "COMPUTER_SOFTWARE").upper()
        normalized_industry = "COMPUTER_SOFTWARE"
        for ind in ALLOWED_INDUSTRIES:
            if ind in industry or industry in ind:
                normalized_industry = ind
                break

        payload = {
            "properties": {
                "name": co["name"],
                "domain": co["domain"],
                "industry": normalized_industry,
                "lifecyclestage": co["lifecyclestage"],
                "hs_lead_status": co["hs_lead_status"]
            }
        }
        res = requests.post("https://api.hubapi.com/crm/v3/objects/companies", headers=HS_HEADERS, json=payload)
        if res.status_code == 201:
            real_id = res.json()["id"]
            company_mappings[co["hs_object_id"]] = real_id
            co["hs_object_id"] = real_id  # Update local JSON model with real ID
            print(f"  ✅ Created Company: {co['name']} (ID: {real_id})")
        else:
            print(f"  ❌ Failed to create Company {co['name']}: {res.text}")
        time.sleep(0.15)  # Respect rate limits

    # Save companies with updated real IDs
    with open("data/raw/hubspot_companies.json", "w") as f:
        json.dump(companies, f, indent=2)

    # 3. Seed Contacts (and associate with real Company IDs)
    print(f"\n👤 Seeding {len(contacts)} contacts to HubSpot...")
    for ct in contacts:
        mock_co_id = ct.get("associated_company_id")
        real_co_id = company_mappings.get(mock_co_id)
        
        payload = {
            "properties": {
                "email": ct["email"],
                "firstname": ct["firstname"],
                "lastname": ct["lastname"],
                "jobtitle": ct["jobtitle"]
            }
        }
        
        # Add association if matched
        if real_co_id:
            payload["associations"] = [
                {
                    "to": {"id": real_co_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 1  # Contact to Company
                        }
                    ]
                }
            ]
            ct["associated_company_id"] = real_co_id

        res = requests.post("https://api.hubapi.com/crm/v3/objects/contacts", headers=HS_HEADERS, json=payload)
        if res.status_code == 201:
            real_id = res.json()["id"]
            ct["hs_object_id"] = real_id  # Update local JSON model with real ID
            print(f"  ✅ Created Contact: {ct['email']} (Real ID: {real_id})")
        elif res.status_code == 409:
            # Already exists — fetch their ID and update local JSON
            existing_id = res.json().get("message", "").split("ID: ")[-1].strip()
            ct["hs_object_id"] = existing_id
            print(f"  ℹ️  Contact already exists: {ct['email']} (Real ID: {existing_id})")
        else:
            print(f"  ❌ Failed to create Contact {ct['email']}: {res.text}")
        time.sleep(0.15)

    # Save contacts with updated real IDs
    with open("data/raw/hubspot_contacts.json", "w") as f:
        json.dump(contacts, f, indent=2)

    # 4. Seed Deals (and associate with real Company IDs)
    print(f"\n💸 Seeding {len(deals)} deals to HubSpot...")
    for dl in deals:
        mock_co_id = dl.get("associated_company_id")
        real_co_id = company_mappings.get(mock_co_id)
        
        stage = dl["dealstage"]
        if stage not in ["closedwon", "closedlost"]:
            stage = "appointmentscheduled"
            
        payload = {
            "properties": {
                "dealname": dl["dealname"],
                "dealstage": stage,
                "amount": str(dl["amount"]),
                "pipeline": "default",
                "closedate": dl.get("closedate")
            }
        }
        
        if real_co_id:
            payload["associations"] = [
                {
                    "to": {"id": real_co_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 5  # Deal to Company
                        }
                    ]
                }
            ]
            dl["associated_company_id"] = real_co_id

        res = requests.post("https://api.hubapi.com/crm/v3/objects/deals", headers=HS_HEADERS, json=payload)
        if res.status_code == 201:
            real_id = res.json()["id"]
            dl["hs_object_id"] = real_id  # Update local JSON model with real ID
            print(f"  ✅ Created Deal: {dl['dealname']} (Real ID: {real_id})")
        else:
            print(f"  ❌ Failed to create Deal {dl['dealname']}: {res.text}")
        time.sleep(0.15)

    # Save deals with updated real IDs
    with open("data/raw/hubspot_deals.json", "w") as f:
        json.dump(deals, f, indent=2)
            
    print("🎉 HubSpot seeding and ID synchronization complete.")


def seed_zendesk():
    if not ZENDESK_SUBDOMAIN or not ZENDESK_API_TOKEN or ZENDESK_API_TOKEN == "mock_token":
        print("⏭️  Skipping Zendesk seeding: credentials are missing or mock.")
        return

    print("\n🚀 Starting Zendesk seeding...")
    with open("data/raw/zendesk_tickets.json", "r") as f:
        tickets = json.load(f)

    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json"

    for tk in tickets:
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
                    "body": f"System generated ticket for {tk.get('requester_email')}."
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
            tk["ticket_id"] = ticket_id  # Update local JSON model
            print(f"  ✅ Created Zendesk Ticket #{ticket_id}: \"{tk['subject']}\"")
        else:
            print(f"  ❌ Failed to create Ticket \"{tk['subject']}\": {res.text}")
        time.sleep(0.2)

    with open("data/raw/zendesk_tickets.json", "w") as f:
        json.dump(tickets, f, indent=2)
    print("🎉 Zendesk seeding complete.")


if __name__ == "__main__":
    print("🌟 GTM Seeding and ID Sync Utility started.")
    seed_hubspot()
    seed_zendesk()
    print("\n✨ Seeding process finished. Local raw data files synced with real HubSpot IDs.")
