"""
reverse_etl_dlt.py
==================
Reads actionable insights from Snowflake Data Warehouse (or local DuckDB) and pushes them
back into HubSpot CRM (the "Reverse ETL" loop).

WHAT IT SYNCS:
  1. Company Enrichment  — Pushes health_status, MRR, segment to HubSpot Companies
  2. PQL Signals         — Tags HOT contacts with intent_tier + recommended_action
  3. L2A Associations    — Stitches unmatched contacts to their company

PREREQUISITES (HubSpot custom properties must exist):
  Companies: mrr, arr, account_segment, health_status, health_reason,
             subscription_status, is_ready_for_upsell, is_churning_soon
  Contacts:  intent_tier, recommended_action

USAGE:
  python scripts/reverse_etl_dlt.py                  # Live run
  python scripts/reverse_etl_dlt.py --dry-run        # Preview only, no API calls
  python scripts/reverse_etl_dlt.py --resource pql   # Run only one resource
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime

import dlt
import duckdb
import snowflake.connector
from dotenv import load_dotenv
from dlt.common.typing import TDataItems
from dlt.common.schema import TTableSchema
from dlt.sources.helpers import requests

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("reverse_etl")

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
DB_PATH = os.path.join(os.getcwd(), "duckdb", "revops_intelligence.duckdb")
HS_BASE = "https://api.hubapi.com/crm/v3/objects"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def validate_token(dry_run: bool):
    if dry_run:
        logger.info("🔍 DRY RUN mode — no API calls will be made.")
        return

    if not HUBSPOT_ACCESS_TOKEN or "xxxx" in HUBSPOT_ACCESS_TOKEN:
        logger.error(
            "❌ HUBSPOT_ACCESS_TOKEN is missing or is a placeholder.\n"
            "   Set a real token in .env before running live."
        )
        sys.exit(1)

    # Quick connectivity check
    resp = requests.get(
        "https://api.hubapi.com/crm/v3/objects/companies?limit=1",
        headers=HEADERS,
    )
    if resp.status_code == 401:
        logger.error("❌ HubSpot token is invalid (401 Unauthorized).")
        sys.exit(1)
    elif resp.status_code not in (200, 204):
        logger.warning(f"⚠️ HubSpot API check returned {resp.status_code}. Proceeding carefully.")
    else:
        logger.info("✅ HubSpot token verified.")

# ---------------------------------------------------------------------------
# SOURCES — Snowflake or DuckDB reads
# ---------------------------------------------------------------------------

def get_db_cursor():
    """Connects to Snowflake if credentials exist, otherwise local DuckDB."""
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")

    if account and user and password:
        try:
            logger.info("🔌 Connecting to Snowflake Data Warehouse for Reverse ETL...")
            conn = snowflake.connector.connect(
                account=account,
                user=user,
                password=password,
                role=os.getenv("SNOWFLAKE_ROLE", "TRANSFORMER"),
                warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
                database=os.getenv("SNOWFLAKE_DATABASE", "REVOPS_INTELLIGENCE"),
                schema="MARTS",
            )
            return conn.cursor(), "snowflake", conn
        except Exception as err:
            logger.warning(f"⚠️ Snowflake connection attempt failed ({err}). Checking DuckDB fallback...")

    if os.path.exists(DB_PATH):
        logger.info(f"🔌 Connecting to local DuckDB at {DB_PATH}...")
        conn = duckdb.connect(DB_PATH, read_only=True)
        return conn.cursor(), "duckdb", conn
    else:
        logger.warning("⚠️ Neither Snowflake credentials nor DuckDB file found.")
        return None, "none", None


@dlt.source(name="revops_warehouse")
def revops_warehouse_source():
    """Reads actionable data from Snowflake or DuckDB mart layer."""

    @dlt.resource(
        name="company_enrichment",
        write_disposition="merge",
        primary_key="hubspot_company_id",
    )
    def company_enrichment(
        updated_at=dlt.sources.incremental(
            "last_updated_at",
            initial_value=datetime(2000, 1, 1),
        )
    ):
        """Sync dim_accounts health + revenue data to HubSpot Companies."""
        cursor, db_type, conn = get_db_cursor()
        if not cursor:
            logger.warning("No warehouse connection available.")
            yield []
            return

        try:
            table_prefix = "MARTS_marts." if db_type == "snowflake" else "main_marts."
            query = f"""
                SELECT
                    hubspot_company_id,
                    workspace_name,
                    domain,
                    mrr,
                    arr,
                    account_segment,
                    health_status,
                    health_reason,
                    subscription_status,
                    seats_purchased,
                    seats_used,
                    seat_utilization_pct,
                    CAST(is_ready_for_upsell AS VARCHAR)    AS is_ready_for_upsell,
                    CAST(is_churning_soon AS VARCHAR)        AS is_churning_soon,
                    last_updated_at
                FROM {table_prefix}dim_accounts
                WHERE hubspot_company_id IS NOT NULL
                ORDER BY mrr DESC NULLS LAST
            """
            cursor.execute(query)
            columns = [col[0].lower() for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.info(f"[company_enrichment] {len(rows)} companies loaded from {db_type}.")
            yield rows
        finally:
            conn.close()

    @dlt.resource(
        name="pql_signals",
        write_disposition="merge",
        primary_key="hubspot_contact_id",
    )
    def pql_signals():
        """Sync HOT PQL signals to HubSpot Contacts."""
        cursor, db_type, conn = get_db_cursor()
        if not cursor:
            yield []
            return

        try:
            marts_prefix = "MARTS_marts." if db_type == "snowflake" else "main_marts."
            identity_prefix = "MARTS_identity." if db_type == "snowflake" else "main_identity."
            query = f"""
                SELECT
                    u.hubspot_contact_id,
                    u.email,
                    p.intent_tier,
                    p.gtm_priority,
                    p.recommended_action,
                    p.icp_tier,
                    p.gtm_priority_rank
                FROM {marts_prefix}fct_pql_signals p
                JOIN {identity_prefix}int_users_joined u
                    ON p.workspace_id = u.internal_workspace_id
                WHERE p.intent_tier IN ('HOT', 'WARM')
                  AND u.hubspot_contact_id IS NOT NULL
                  AND u.user_role = 'owner'
            """
            cursor.execute(query)
            columns = [col[0].lower() for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.info(f"[pql_signals] {len(rows)} HOT/WARM contacts loaded from {db_type}.")
            yield rows
        finally:
            conn.close()

    @dlt.resource(
        name="l2a_associations",
        write_disposition="merge",
        primary_key="email",
    )
    def l2a_associations():
        """Fix unlinked contacts: associate them with their company in HubSpot."""
        cursor, db_type, conn = get_db_cursor()
        if not cursor:
            yield []
            return

        try:
            identity_prefix = "MARTS_identity." if db_type == "snowflake" else "main_identity."
            query = f"""
                SELECT
                    u.email,
                    u.hubspot_contact_id,
                    u.hubspot_company_id_stitched  AS hubspot_company_id,
                    u.match_method
                FROM {identity_prefix}int_users_joined u
                WHERE u.hubspot_contact_id IS NOT NULL
                  AND u.hubspot_company_id_stitched IS NOT NULL
                  AND u.match_method IN ('email_match', 'domain_l2a')
            """
            cursor.execute(query)
            columns = [col[0].lower() for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.info(f"[l2a_associations] {len(rows)} contacts to associate from {db_type}.")
            yield rows
        finally:
            conn.close()

    return [company_enrichment, pql_signals, l2a_associations]


# ---------------------------------------------------------------------------
# DESTINATION — HubSpot API writer
# ---------------------------------------------------------------------------

_DRY_RUN: bool = False


@dlt.destination(name="hubspot_api", batch_size=20)
def hubspot_api_destination(items: TDataItems, table: TTableSchema) -> None:
    """
    Custom dlt destination: writes each batch to the HubSpot API.
    Uses PATCH for companies/contacts (idempotent — safe to re-run).
    """
    table_name = table["name"]
    logger.info(f"\n{'─'*50}")
    logger.info(f"📤 Syncing {len(items)} items → {table_name}")

    for item in items:
        try:
            if table_name == "company_enrichment":
                _sync_company(item)
            elif table_name == "pql_signals":
                _sync_pql_contact(item)
            elif table_name == "l2a_associations":
                _sync_l2a(item)
        except Exception as e:
            logger.error(f"   ❌ Failed item ({table_name}): {e}")
            raise


def _patch(url: str, payload: dict, label: str):
    """PATCH a HubSpot object. Handles rate limits with exponential backoff."""
    if _DRY_RUN:
        logger.info(f"   [DRY RUN] PATCH {url}\n   Payload: {payload}")
        return

    for attempt in range(1, 4):
        resp = requests.patch(url, headers=HEADERS, json=payload)
        if resp.status_code == 200:
            logger.info(f"   ✅ {label}")
            return
        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2))
            logger.warning(f"   ⏳ Rate limited. Waiting {retry_after}s (attempt {attempt}/3)...")
            time.sleep(retry_after)
        else:
            logger.warning(f"   ⚠️ {label} → {resp.status_code}: {resp.text[:200]}")
            return

    logger.error(f"   ❌ Gave up after 3 attempts: {label}")


def _sync_company(item: dict):
    """PATCH a HubSpot Company with fresh health, MRR, segment data."""
    company_id = item["hubspot_company_id"]
    url = f"{HS_BASE}/companies/{company_id}"

    payload = {
        "properties": {
            "name":                 item.get("workspace_name", ""),
            "domain":               item.get("domain", ""),
            "mrr":                  str(round(float(item.get("mrr") or 0), 2)),
            "arr":                  str(round(float(item.get("arr") or 0), 2)),
            "account_segment":      item.get("account_segment") or "",
            "health_status":        item.get("health_status") or "",
            "health_reason":        item.get("health_reason") or "",
            "subscription_status":  item.get("subscription_status") or "",
            "is_ready_for_upsell":  str(item.get("is_ready_for_upsell") or "false").lower(),
            "is_churning_soon":     str(item.get("is_churning_soon") or "false").lower(),
        }
    }
    label = (
        f"Company {item.get('workspace_name', company_id)} | "
        f"MRR=${float(item.get('mrr') or 0):.0f} | "
        f"Health={item.get('health_status')}"
    )
    _patch(url, payload, label)


def _sync_pql_contact(item: dict):
    """PATCH a HubSpot Contact with PQL intent tier and recommended action."""
    contact_id = item["hubspot_contact_id"]
    url = f"{HS_BASE}/contacts/{contact_id}"

    payload = {
        "properties": {
            "intent_tier":          item.get("intent_tier", ""),
            "recommended_action":   item.get("recommended_action", ""),
            "gtm_priority":         item.get("gtm_priority", ""),
            "icp_tier":             item.get("icp_tier", ""),
            "gtm_priority_rank":    str(item.get("gtm_priority_rank") or ""),
        }
    }
    label = (
        f"Contact {item.get('email', contact_id)} | "
        f"Intent={item.get('intent_tier')} | "
        f"GTM={item.get('gtm_priority')}"
    )
    _patch(url, payload, label)


def _sync_l2a(item: dict):
    """Associate a Contact with their Company (L2A stitching)."""
    contact_id = item["hubspot_contact_id"]
    company_id = item["hubspot_company_id"]

    if _DRY_RUN:
        logger.info(
            f"   [DRY RUN] PUT association: "
            f"Contact {item.get('email')} ({item.get('match_method')}) "
            f"→ Company {company_id}"
        )
        return

    url = f"{HS_BASE}/contacts/{contact_id}/associations/companies/{company_id}/0-1"
    resp = requests.put(url, headers=HEADERS)
    if resp.status_code in (200, 204):
        logger.info(
            f"   🔗 Associated {item.get('email')} ({item.get('match_method')}) "
            f"→ Company {company_id}"
        )
    elif resp.status_code == 429:
        time.sleep(2)
    else:
        logger.warning(f"   ⚠️ Association failed: {resp.status_code} {resp.text[:150]}")


# ---------------------------------------------------------------------------
# PIPELINE RUNNER
# ---------------------------------------------------------------------------

RESOURCE_MAP = {
    "companies": "company_enrichment",
    "pql":       "pql_signals",
    "l2a":       "l2a_associations",
    "all":       None,
}


def run(dry_run: bool = False, resource: str = "all"):
    """
    Main entry point.
    Pipeline state is stored in .dlt/ directory (JSON, gitignored).
    Enables incremental loading: only changed records are synced each run.
    """
    global _DRY_RUN
    _DRY_RUN = dry_run

    validate_token(dry_run)

    logger.info("=" * 60)
    logger.info("🔄 Reverse ETL: Data Warehouse → HubSpot CRM")
    logger.info(f"   Mode     : {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"   Resource : {resource}")
    logger.info("=" * 60)

    pipeline = dlt.pipeline(
        pipeline_name="revops_to_hubspot",
        destination=hubspot_api_destination,
        dataset_name="hubspot_sync",
    )

    source = revops_warehouse_source()

    selected = RESOURCE_MAP.get(resource)
    if selected:
        source = source.with_resources(selected)

    info = pipeline.run(source)

    logger.info("\n" + "=" * 60)
    logger.info("🏁 Reverse ETL Complete")
    logger.info(f"   Rows processed : {info.metrics}")
    logger.info("=" * 60)

    return info


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reverse ETL: Data Warehouse → HubSpot CRM"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be synced without making any API calls.",
    )
    parser.add_argument(
        "--resource",
        choices=["all", "companies", "pql", "l2a"],
        default="all",
        help=(
            "Which resource to sync:\n"
            "  companies — health/MRR to HubSpot Companies\n"
            "  pql       — intent tags to HubSpot Contacts\n"
            "  l2a       — contact-company associations\n"
            "  all       — all three (default)"
        ),
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, resource=args.resource)
