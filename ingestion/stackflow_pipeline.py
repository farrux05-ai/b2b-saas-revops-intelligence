import dlt
import json
from pathlib import Path

def load_json(filename):
    path = Path("data/raw") / filename
    with open(path, "r") as f:
        return json.load(f)

@dlt.source(name="hubspot")
def hubspot_source():
    return [
        dlt.resource(load_json("hubspot_companies.json"), name="companies", write_disposition="replace"),
        dlt.resource(load_json("hubspot_deals.json"), name="deals", write_disposition="replace"),
        dlt.resource(load_json("hubspot_contacts.json"), name="contacts", write_disposition="replace"),
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

def run_pipeline():
    pipeline = dlt.pipeline(
        pipeline_name="revops_intelligence",
        destination=dlt.destinations.duckdb("duckdb/revops_intelligence.duckdb"),
        dataset_name="raw_data",
    )

    # Run sources
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
