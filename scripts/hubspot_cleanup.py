"""
hubspot_cleanup.py
==================
Deletes ALL existing Contacts and Companies from HubSpot CRM
before seeding fresh data from the DuckDB warehouse.

⚠️  WARNING: This is destructive. It permanently deletes records.
    Only use on a sandbox/demo HubSpot account.

Usage:
    python scripts/hubspot_cleanup.py
"""

import os
import time
import logging
from dotenv import load_dotenv
from dlt.sources.helpers import requests

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("hubspot_cleanup")

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")

if not HUBSPOT_ACCESS_TOKEN or "xxxx" in HUBSPOT_ACCESS_TOKEN:
    raise EnvironmentError(
        "❌ HUBSPOT_ACCESS_TOKEN not set or is a placeholder. "
        "Set a real token in .env before running cleanup."
    )

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

BASE_URL = "https://api.hubapi.com/crm/v3/objects"


# ---------------------------------------------------------------------------
# BATCH DELETE HELPERS
# ---------------------------------------------------------------------------

def fetch_all_ids(object_type: str) -> list[str]:
    """Fetches all object IDs (contacts or companies) using pagination."""
    ids = []
    url = f"{BASE_URL}/{object_type}"
    params = {"limit": 100, "properties": "hs_object_id"}
    
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        results = data.get("results", [])
        ids.extend([r["id"] for r in results])
        
        paging = data.get("paging", {}).get("next", {})
        if paging.get("after"):
            params["after"] = paging["after"]
        else:
            break
        
        # Rate limit safety: 10 requests/second
        time.sleep(0.1)
    
    return ids


def batch_delete(object_type: str, ids: list[str]) -> int:
    """
    Deletes records using HubSpot's batch delete API.
    Max 100 records per batch request.
    Returns total deleted count.
    """
    if not ids:
        logger.info(f"  No {object_type} to delete.")
        return 0
    
    deleted = 0
    url = f"{BASE_URL}/{object_type}/batch/archive"
    
    # Chunk into batches of 100 (HubSpot limit)
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        payload = {"inputs": [{"id": id_} for id_ in chunk]}
        
        resp = requests.post(url, headers=HEADERS, json=payload)
        
        if resp.status_code == 204:
            deleted += len(chunk)
            logger.info(f"  ✅ Deleted batch {i//100 + 1}: {len(chunk)} {object_type}")
        else:
            logger.warning(
                f"  ⚠️ Batch delete warning for {object_type}: "
                f"{resp.status_code} → {resp.text[:200]}"
            )
        
        # Rate limit safety
        time.sleep(0.2)
    
    return deleted


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def cleanup_hubspot():
    """Full cleanup: deletes all Contacts first, then all Companies."""
    
    logger.info("=" * 60)
    logger.info("🗑️  HubSpot CRM Cleanup Starting")
    logger.info("=" * 60)

    # --- Step 1: Delete Contacts ---
    logger.info("📋 Fetching all Contacts...")
    contact_ids = fetch_all_ids("contacts")
    logger.info(f"  Found {len(contact_ids)} contacts to delete.")
    
    deleted_contacts = batch_delete("contacts", contact_ids)
    logger.info(f"✅ Contacts deleted: {deleted_contacts}")

    # Small pause before companies (contacts must be removed first
    # to avoid orphaned associations)
    time.sleep(1)

    # --- Step 2: Delete Companies ---
    logger.info("🏢 Fetching all Companies...")
    company_ids = fetch_all_ids("companies")
    logger.info(f"  Found {len(company_ids)} companies to delete.")
    
    deleted_companies = batch_delete("companies", company_ids)
    logger.info(f"✅ Companies deleted: {deleted_companies}")

    logger.info("=" * 60)
    logger.info(f"🏁 Cleanup complete. Removed {deleted_contacts} contacts, {deleted_companies} companies.")
    logger.info("   HubSpot is now ready for fresh data seeding.")
    logger.info("=" * 60)


if __name__ == "__main__":
    cleanup_hubspot()
