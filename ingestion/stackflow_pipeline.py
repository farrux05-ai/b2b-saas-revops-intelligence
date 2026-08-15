"""
stackflow_pipeline.py
=====================
DEV ELT Pipeline: Ingests mock JSON raw data into Snowflake RAW_DATA schema using dlt.

SOURCES INGESTED:
  - HubSpot CRM (companies, deals, contacts, engagements)
  - Stripe Billing (subscriptions, invoices, payments)
  - Internal DB (workspaces, users, events)
  - Zendesk Support (tickets)

DESTINATION:
  Snowflake Warehouse -> RAW_DATA schema
"""

import json
import os
from pathlib import Path
import dlt
from dotenv import load_dotenv
from dlt.destinations.impl.snowflake.configuration import SnowflakeCredentials

# Always load .env from the project root, regardless of where script is invoked from
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

def load_json(filename):
    path = Path("data/raw") / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@dlt.source(name="hubspot")
def hubspot_source():
    return [
        dlt.resource(load_json("hubspot_companies.json"), name="companies", write_disposition="replace"),
        dlt.resource(load_json("hubspot_deals.json"), name="deals", write_disposition="replace"),
        dlt.resource(load_json("hubspot_contacts.json"), name="contacts", write_disposition="replace"),
        dlt.resource(load_json("hubspot_engagements.json"), name="engagements", write_disposition="replace"),
    ]

@dlt.source(name="stripe")
def stripe_source():
    return [
        dlt.resource(load_json("stripe_subscriptions.json"), name="subscriptions", write_disposition="replace"),
        dlt.resource(load_json("stripe_invoices.json"), name="invoices", write_disposition="replace"),
        dlt.resource(load_json("stripe_payments.json"), name="payments", write_disposition="replace"),
    ]

@dlt.source(name="internal")
def internal_db_source():
    return [
        dlt.resource(load_json("internal_workspaces.json"), name="workspaces", write_disposition="replace"),
        dlt.resource(load_json("internal_users.json"), name="users", write_disposition="replace"),
        dlt.resource(load_json("internal_events.json"), name="events", write_disposition="replace"),
    ]

@dlt.source(name="zendesk")
def zendesk_source():
    return [
        dlt.resource(load_json("zendesk_tickets.json"), name="tickets", write_disposition="replace"),
    ]

def get_destination():
    """
    Builds a SnowflakeCredentials object directly from .env variables.
    This bypasses dlt's config resolution pipeline entirely — no secrets.toml,
    no env var parsing ambiguity, no URL encoding issues.
    """
    account   = os.getenv("SNOWFLAKE_ACCOUNT", "")
    user      = os.getenv("SNOWFLAKE_USER", "")
    password  = os.getenv("SNOWFLAKE_PASSWORD", "")
    database  = os.getenv("SNOWFLAKE_DATABASE", "REVOPS_INTELLIGENCE")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    role      = os.getenv("SNOWFLAKE_ROLE", "TRANSFORMER")

    if not (account and user and password):
        raise RuntimeError(
            "Missing Snowflake credentials in .env — "
            "set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD"
        )

    print(f"[dlt] Connecting: {user}@{account}/{database}  warehouse={warehouse}  role={role}")

    # Build credentials object directly — no resolution/parsing needed
    creds = SnowflakeCredentials()
    creds.host      = account   # e.g. zu12882.me-central2.gcp
    creds.username  = user
    creds.password  = password
    creds.database  = database
    creds.warehouse = warehouse
    creds.role      = role

    return dlt.destinations.snowflake(credentials=creds)


def run_pipeline():
    destination = get_destination()
    pipeline = dlt.pipeline(
        pipeline_name="revops_intelligence_ingestion",
        destination=destination,
        dataset_name="raw_data",
    )

    # Run sources into Snowflake RAW_DATA schema
    info = pipeline.run(hubspot_source())
    print(f"HubSpot: {info}")

    info = pipeline.run(stripe_source())
    print(f"Stripe: {info}")

    info = pipeline.run(internal_db_source())
    print(f"Internal: {info}")

    info = pipeline.run(zendesk_source())
    print(f"Zendesk: {info}")

if __name__ == "__main__":
    run_pipeline()
