"""
hubspot_seed.py
===============
Reads fresh accounts data from DuckDB (dim_accounts + int_users_joined)
and creates Companies + Contacts in HubSpot CRM from scratch.

This is the "initial load" step — run ONCE after cleanup.
After this, the daily Reverse ETL (reverse_etl_dlt.py) handles updates.

Flow:
    DuckDB dim_accounts  →  HubSpot Companies  (1 company per account)
    DuckDB int_users_joined  →  HubSpot Contacts  (owner user per account)
    Contact → Company Association

Usage:
    python scripts/hubspot_seed.py
    python scripts/hubspot_seed.py --dry-run   (shows what would happen, no API calls)
"""

import os
import sys
import time
import argparse
import logging
import duckdb
from dotenv import load_dotenv
from dlt.sources.helpers import requests

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("hubspot_seed")

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
DB_PATH = os.path.join(os.getcwd(), "duckdb", "revops_intelligence.duckdb")

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com/crm/v3/objects"


# ---------------------------------------------------------------------------
# DATA EXTRACTION FROM DUCKDB
# ---------------------------------------------------------------------------

def get_accounts() -> list[dict]:
    """Pull all active accounts from dim_accounts."""
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("""
        SELECT
            account_id,
            hubspot_company_id,      -- may be NULL (new accounts)
            workspace_name,
            domain,
            mrr,
            arr,
            account_segment,
            subscription_status,
            health_status,
            health_reason,
            seat_utilization_pct,
            is_ready_for_upsell,
            is_churning_soon,
            seats_purchased,
            seats_used
        FROM main_marts.dim_accounts
        WHERE subscription_status IN ('active', 'trialing', 'past_due')
        ORDER BY mrr DESC NULLS LAST
    """).df().to_dict("records")
    con.close()
    logger.info(f"📦 Loaded {len(rows)} accounts from DuckDB")
    return rows


def get_owner_users() -> dict[str, dict]:
    """Pull one owner user per workspace from int_users_joined → keyed by workspace_id."""
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("""
        SELECT DISTINCT ON (internal_workspace_id)
            internal_workspace_id,
            email,
            hubspot_contact_id,
            match_method
        FROM main_identity.int_users_joined
        WHERE user_role = 'owner'
          AND email IS NOT NULL
        ORDER BY internal_workspace_id, match_method DESC
    """).df().to_dict("records")
    con.close()
    logger.info(f"👤 Loaded {len(rows)} owner users from DuckDB")
    return {r["internal_workspace_id"]: r for r in rows}


# ---------------------------------------------------------------------------
# HUBSPOT API HELPERS
# ---------------------------------------------------------------------------

def create_company(account: dict, dry_run: bool) -> str | None:
    """Creates one HubSpot Company and returns its new hubspot_company_id."""
    payload = {
        "properties": {
            "name": account["workspace_name"],
            "domain": account.get("domain") or "",
            # Custom RevOps properties (must exist in HubSpot portal)
            "mrr": str(round(account.get("mrr") or 0, 2)),
            "arr": str(round(account.get("arr") or 0, 2)),
            "account_segment": account.get("account_segment") or "Unknown",
            "health_status": account.get("health_status") or "Unknown",
            "health_reason": account.get("health_reason") or "",
            "subscription_status": account.get("subscription_status") or "",
            "is_ready_for_upsell": str(account.get("is_ready_for_upsell") or False).lower(),
            "is_churning_soon": str(account.get("is_churning_soon") or False).lower(),
        }
    }

    if dry_run:
        logger.info(f"  [DRY RUN] Would create company: {account['workspace_name']} (MRR: ${account.get('mrr', 0):.0f})")
        return "dry_run_id"

    resp = requests.post(f"{BASE_URL}/companies", headers=HEADERS, json=payload)
    if resp.status_code == 201:
        company_id = resp.json()["id"]
        logger.info(f"  ✅ Created Company: {account['workspace_name']} → HS ID: {company_id}")
        return company_id
    else:
        logger.warning(f"  ⚠️ Failed to create {account['workspace_name']}: {resp.text[:200]}")
        return None


def create_contact(email: str, dry_run: bool) -> str | None:
    """Creates a Contact in HubSpot. Returns contact ID."""
    payload = {"properties": {"email": email}}

    if dry_run:
        logger.info(f"  [DRY RUN] Would create contact: {email}")
        return "dry_run_id"

    resp = requests.post(f"{BASE_URL}/contacts", headers=HEADERS, json=payload)
    if resp.status_code == 201:
        contact_id = resp.json()["id"]
        logger.info(f"  ✅ Created Contact: {email} → HS ID: {contact_id}")
        return contact_id
    elif resp.status_code == 409:
        # Already exists — fetch their ID
        existing_id = resp.json().get("message", "").split("ID: ")[-1].strip()
        logger.info(f"  ℹ️  Contact already exists: {email} → HS ID: {existing_id}")
        return existing_id
    else:
        logger.warning(f"  ⚠️ Failed to create contact {email}: {resp.text[:200]}")
        return None


def associate_contact_company(contact_id: str, company_id: str, dry_run: bool):
    """Associates a Contact with a Company in HubSpot."""
    if dry_run:
        logger.info(f"  [DRY RUN] Would associate contact {contact_id} → company {company_id}")
        return

    url = (
        f"{BASE_URL}/contacts/{contact_id}"
        f"/associations/companies/{company_id}/0-1"
    )
    resp = requests.put(url, headers=HEADERS)
    if resp.status_code in (200, 204):
        logger.info(f"  🔗 Associated Contact {contact_id} with Company {company_id}")
    else:
        logger.warning(f"  ⚠️ Association failed: {resp.text[:200]}")


# ---------------------------------------------------------------------------
# MAIN SEED FLOW
# ---------------------------------------------------------------------------

def seed_hubspot(dry_run: bool = False):
    """
    Full seed flow:
        1. Read dim_accounts from DuckDB
        2. For each account → create HubSpot Company
        3. For each account → find owner user → create HubSpot Contact
        4. Associate Contact → Company
    """
    mode = "🔍 DRY RUN" if dry_run else "🚀 LIVE"
    logger.info("=" * 60)
    logger.info(f"{mode}: HubSpot Data Seeding Starting")
    logger.info("=" * 60)

    if not dry_run and (not HUBSPOT_ACCESS_TOKEN or "xxxx" in HUBSPOT_ACCESS_TOKEN):
        raise EnvironmentError(
            "❌ HUBSPOT_ACCESS_TOKEN is not set. Cannot run live seed."
        )

    accounts = get_accounts()
    users_by_workspace = get_owner_users()

    created_companies = 0
    created_contacts = 0
    associated = 0

    for account in accounts:
        workspace_id = account["account_id"]
        logger.info(f"\n── Account: {account['workspace_name']} (MRR: ${account.get('mrr', 0):.0f}/mo)")

        # Step A: Create Company
        company_id = create_company(account, dry_run)
        if company_id:
            created_companies += 1

        # Step B: Find & Create owner Contact
        owner = users_by_workspace.get(workspace_id)
        contact_id = None
        if owner and owner.get("email"):
            contact_id = create_contact(owner["email"], dry_run)
            if contact_id:
                created_contacts += 1

        # Step C: Associate
        if company_id and contact_id and not dry_run:
            associate_contact_company(contact_id, company_id, dry_run)
            associated += 1

        # Rate limit: max ~5 account-operations/second
        time.sleep(0.3)

    logger.info("\n" + "=" * 60)
    logger.info(f"🏁 Seeding {'(DRY RUN) ' if dry_run else ''}complete.")
    logger.info(f"   Companies created : {created_companies}")
    logger.info(f"   Contacts  created : {created_contacts}")
    logger.info(f"   Associations made : {associated}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed HubSpot from DuckDB warehouse")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without making any API calls",
    )
    args = parser.parse_args()
    seed_hubspot(dry_run=args.dry_run)
