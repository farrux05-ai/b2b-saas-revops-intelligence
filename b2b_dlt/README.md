# B2B dlt Pipelines

A unified [dlt](https://dlthub.com/) (data load tool) pipeline orchestrator for a B2B RevOps data stack.
Loads data from all source systems into a MotherDuck data warehouse.

## Architecture

```
main.py                    ← single entry point (CLI)
pipelines/
  posthog.py               ← PostHog (persons, insights, cohorts, ...)
  hubspot.py               ← HubSpot CRM (contacts, companies, deals, tickets + property history)
  zendesk.py               ← Zendesk (Support + Chat + Talk, incremental)
  stripe.py                ← Stripe Analytics (all payment endpoints)
  pg_replication.py        ← PostgreSQL CDC (logical replication)
hubspot/                   ← dlt source connector (unchanged)
zendesk/                   ← dlt source connector (unchanged)
stripe_analytics/          ← dlt source connector (unchanged)
pg_replication/            ← dlt source connector (unchanged)
.dlt/
  config.toml              ← non-secret configuration (project IDs, hosts, ...)
  secrets.toml             ← credentials (API keys, DB passwords) — never commit
```

## Installation

```bash
uv sync
# or
pip install -e .
```

## Usage

```bash
# Run all pipelines sequentially
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

[destination.motherduck.credentials]
database = "my_db"
password = "your_motherduck_token"
```

## Datasets & Tables

| Pipeline | MotherDuck Dataset | Key Tables |
|---|---|---|
| posthog | `posthog_data` | persons, insights, dashboards, cohorts |
| hubspot | `hubspot_dataset` | contacts, companies, deals, tickets + property_history |
| zendesk | `zendesk_data` | tickets, users, organizations, chats |
| stripe | `stripe_data` | charges, customers, invoices, subscriptions |
| pg_replication | `pg_replicated_data` | (mirrors your source tables) |

## Scheduling with Cron

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
