# B2B dlt Pipelines

A unified [dlt](https://dlthub.com/) (data load tool) pipeline orchestrator for a B2B RevOps data stack.
Loads data from all source systems into a Snowflake data warehouse.

## Architecture

```
main.py                    ← single entry point (CLI)
pipelines/
  posthog.py               ← PostHog (persons, insights, cohorts, ...)
  hubspot.py               ← HubSpot CRM (contacts, companies, deals, tickets + property history)
  zendesk.py               ← Zendesk (Support + Chat + Talk, incremental)
  stripe.py                ← Stripe Analytics (all payment endpoints)
  pg_replication.py        ← PostgreSQL CDC (logical replication)
hubspot/                   ← dlt source connector
zendesk/                   ← dlt source connector
stripe_analytics/          ← dlt source connector
pg_replication/            ← dlt source connector
.dlt/
  config.toml              ← non-secret configuration
  secrets.toml             ← credentials (API keys, DB passwords) — never commit
```

## Installation

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e .
```

## Usage

```bash
# Run all pipelines sequentially into Snowflake
python main.py

# Run a single pipeline
python main.py --pipeline posthog
python main.py --pipeline hubspot
python main.py --pipeline zendesk
python main.py --pipeline stripe
python main.py --pipeline pg_replication

# Run multiple selected pipelines
python main.py --pipeline posthog hubspot

# Enable debug logging
python main.py --log-level DEBUG
```

## Configuration

### `.dlt/config.toml`

```toml
[runtime]
log_level = "WARNING"

[sources.posthog]
project_id = "YOUR_PROJECT_ID"
host = "https://eu.posthog.com"   # or https://us.posthog.com
```

### `.dlt/secrets.toml`

```toml
[sources.posthog]
api_key = "phx_..."               # Personal API Key (phx_ prefix required)

[sources.hubspot]
api_key = "..."                   # HubSpot Private App Token

[sources.zendesk.credentials]
subdomain = "yourcompany"
email = "admin@example.com"
password = "your_api_token"       # Zendesk API Token

[sources.stripe_analytics]
stripe_secret_key = "sk_live_..."

[sources.pg_replication.credentials]
drivername = "postgresql"
host = "localhost"
port = 5432
database = "your_db"
username = "your_user"
password = "your_password"

[destination.snowflake.credentials]
account = "xy12345.us-east-1"
user = "TRANSFORMER"
password = "your_snowflake_password"
database = "REVOPS_INTELLIGENCE"
schema = "RAW_DATA"
```

## Datasets & Tables (Snowflake Schema: RAW_DATA)

| Pipeline | Snowflake Destination Schema | Key Tables |
|---|---|---|
| posthog | `RAW_DATA` | persons, insights, dashboards, cohorts |
| hubspot | `RAW_DATA` | contacts, companies, deals, tickets, property_history |
| zendesk | `RAW_DATA` | tickets, users, organizations, chats |
| stripe | `RAW_DATA` | charges, customers, invoices, subscriptions |
| pg_replication | `RAW_DATA` | (mirrors source PostgreSQL tables) |

## Scheduling with Dagster or Cron

```cron
# Run all pipelines every night at 02:00
0 2 * * * cd /path/to/b2b_dlt && .venv/bin/python main.py >> /var/log/dlt/pipeline.log 2>&1
```

## PostHog API Key Note

`phc_...` keys are **Project (Ingestion) API Keys** — they are write-only and cannot
read data. To use this pipeline you need a **Personal API Key** (`phx_...`) with
at minimum these scopes: `person:read`, `feature_flag:read`, `cohort:read`,
`insight:read`, `dashboard:read`, `experiment:read`, `action:read`, `annotation:read`.

Create one at **PostHog → Settings → Personal API Keys**.
