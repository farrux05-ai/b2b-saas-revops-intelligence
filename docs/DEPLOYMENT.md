# Deployment Runbook: RevOps Intelligence Engine

This document covers end-to-end deployment of all pipeline components: local development, cloud warehouse, BI layer, and orchestration.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Local Pipeline Run](#2-local-pipeline-run)
3. [MotherDuck Configuration](#3-motherduck-configuration)
4. [Lightdash Setup](#4-lightdash-setup)
5. [Dagster Scheduling](#5-dagster-scheduling)
6. [Slack Bot Integration](#6-slack-bot-integration)
7. [CI/CD & dbt Docs (GitHub Pages)](#7-cicd--dbt-docs-github-pages)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Environment Setup

### Python Environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### Environment Variables

Copy the template and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

```env
# MotherDuck (Cloud DuckDB)
MOTHERDUCK_TOKEN=your_motherduck_token_here

# HubSpot Reverse ETL
# Use a real PAT for live sync; leave as placeholder for mock mode
# Mock mode is automatically detected if token contains "xxxx"
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxx-xxxx-xxxx-xxxx

# Zendesk (optional — used for source freshness only)
ZENDESK_API_TOKEN=your_zendesk_token
```

> **Mock Mode:** `reverse_etl_dlt.py` automatically detects placeholder tokens (containing `"xxxx"` or equal to `"mock_token"`) and skips live API calls. All sync logs show `Mock: True`. Safe for local development and CI runs.

### dbt Profile

`profiles.yml` is pre-configured for local DuckDB:

```yaml
revops_intelligence_engine:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "{{ env_var('DBT_DUCKDB_PATH', 'duckdb/revops_intelligence.duckdb') }}"
      threads: 4
```

No changes needed for local development.

---

## 2. Local Pipeline Run

### Step 1: Generate or Refresh Mock Data

```bash
python scripts/generate_mock_data.py
```

Populates `raw_data` schema in `duckdb/revops_intelligence.duckdb` with realistic mock data for all sources (HubSpot, Stripe, Zendesk, PostHog, Internal DB).

### Step 2: Run dbt

```bash
# Full build (recommended)
dbt build --store-failures

# Build only specific layers
dbt build --select staging
dbt build --select intermediate
dbt build --select marts

# Run tests only
dbt test

# Check source freshness
dbt source freshness
```

### Step 3: Sync to MotherDuck

```bash
python scripts/sync_to_motherduck.py
```

Uses DuckDB's native `ATTACH` + `CREATE OR REPLACE TABLE AS SELECT *` to copy 40 tables in dependency order: `raw_data` → `main_marts` → `main_staging`.

> **Important:** Schema sync order matters. `raw_data` must sync before `main_staging` because staging views reference raw table columns by name. Reversing the order causes `Binder Error: column not found` during view evaluation.

### Step 4: Reverse ETL to HubSpot

```bash
python scripts/reverse_etl_dlt.py
```

Reads from local DuckDB and pushes to HubSpot API:
- `hubspot_l2a_associations` — heals missing Contact→Company associations
- `hubspot_pql_signals` — updates intent tier and recommended action on contacts
- `hubspot_company_enrichment` — syncs health_status, MRR, and segment to company records

---

## 3. MotherDuck Configuration

### Getting a Token

1. Go to [app.motherduck.com](https://app.motherduck.com)
2. Navigate to **Settings → Access Tokens**
3. Create a new token with Read/Write access
4. Copy the token into your `.env` as `MOTHERDUCK_TOKEN`

### Verifying Connection

```python
import os, duckdb
from dotenv import load_dotenv
load_dotenv()

os.environ["MOTHERDUCK_TOKEN"] = os.getenv("MOTHERDUCK_TOKEN")
con = duckdb.connect("md:revops_intelligence")

# Should show: raw_data, main_marts, main_staging schemas
print(con.execute("SELECT schema_name FROM information_schema.schemata").df())

# Verify row counts
print(con.execute("SELECT count(*) FROM main_marts.fct_accounts_health").fetchone())
con.close()
```

### Schema Structure in MotherDuck

| Schema | Contents | Row Count (approx.) |
|:-------|:---------|:-------------------|
| `raw_data` | 15 raw source tables | ~10K–15K rows total |
| `main_marts` | 14 mart tables (dims + facts) | ~6K rows total |
| `main_staging` | 11 staging views materialized | ~10K rows total |

---

## 4. Lightdash Setup

### Connect Lightdash to MotherDuck

Lightdash connects to MotherDuck as a DuckDB warehouse:

1. In Lightdash, go to **Settings → Connections → Add project**
2. Select **DuckDB**
3. Set connection:
   - **Database path:** `md:revops_intelligence` (MotherDuck URI)
   - **Access token:** your `MOTHERDUCK_TOKEN`
4. Point to your **GitHub repository** for the dbt project
5. Set **dbt project path** to `/` (root of this repo)

### Refresh dbt Project in Lightdash

After any schema YAML changes:

```
Lightdash → Settings → Project → Refresh dbt
```

All new metrics and dimensions defined in `*_schema.yml` files will appear automatically.

### Semantic Layer Reference

Metrics and dimensions are defined in these files:

| File | Models | Key Metrics |
|:-----|:-------|:-----------|
| `models/marts/core/core_schema.yml` | `dim_accounts`, `dim_users`, `dim_dates` | `total_arr`, `total_mrr` |
| `models/marts/customer_success/cs_schema.yml` | `fct_accounts_health` | `at_risk_accounts`, `total_mrr_at_risk`, `upsell_ready_cs` |
| `models/marts/finance/finance_schema.yml` | `fct_mrr_waterfall`, `fct_arr_movements` | `total_arr_movements`, `total_churn_mrr` |
| `models/marts/sales/sales_schema.yml` | `fct_pipeline` | `total_pipeline_value`, `weighted_pipeline_value` |
| `models/marts/marketing/marketing_schema.yml` | `fct_lead_funnel`, `fct_attribution` | `total_leads`, `conversion_rate` |

> **Metric naming:** Finance metrics use the `_movements` suffix to avoid collision with `total_arr` in `core_schema.yml`. Always check for namespace conflicts before adding a new metric.

### Recommended Dashboard & Charts to Create

**CS Dashboard: "Account Health"**
- Pie/Donut: `Account Health` explore → `Health Status` dimension + `Total Accounts (CS)` metric
- Bar: `Account Health` explore → `Segment` dimension + `MRR at Risk` metric → filter: `Health Status = At Risk`
- Table: `Account Health` explore → `Account`, `Plan`, `Upsell Ready` → filter: `is_ready_for_upsell = true`

**Finance Dashboard: "Revenue Intelligence"**
- Line: `fct_arr_movements` explore → `Month Date` + `Total ARR Movements`
- Grouped Bar: `fct_mrr_waterfall` explore → `Month Date` + `new_mrr`, `expansion_mrr`, `contraction_mrr`, `churn_mrr`

---

## 5. Dagster Scheduling

### Running Dagster Locally

```bash
dagster dev -f dagster_pipeline.py
# Open http://localhost:3000
```

### Jobs Available

| Job | Selection | When to Run |
|:----|:----------|:------------|
| `revops_ingestion_job` | `ingestion_dlt` only | When fresh raw data is needed |
| `revops_transform_job` | `revops_dbt_assets` + `motherduck_sync` + `dlt_reverse_etl` | Daily at 07:00 UTC |

### Manual Execution

```bash
# Run ingestion only
dagster job execute -f dagster_pipeline.py -j revops_ingestion_job

# Run full transform pipeline
dagster job execute -f dagster_pipeline.py -j revops_transform_job
```

### Daily Schedule

The pipeline is scheduled to run at **07:00 UTC** every day:

```python
# dagster_pipeline.py
revops_daily_schedule = ScheduleDefinition(
    job=revops_transform_job,
    cron_schedule="0 7 * * *",
    execution_timezone="UTC",
)
```

To activate the schedule in the Dagster UI: **Automation → revops_daily_schedule → Turn on**.

### Test Failure Storage

dbt is configured with `--store-failures`. When a test fails, the failing rows are written to the `main_dbt_test__audit` schema in DuckDB for post-mortem investigation:

```sql
-- Inspect test failures after a failed run
SELECT * FROM main_dbt_test__audit.not_null_fct_mrr_waterfall_account_id LIMIT 50;
```

---

## 6. Slack Bot Integration

Lightdash's native Slack integration enables scheduled dashboard deliveries and AI-powered Q&A.

### Setup Steps

1. In Lightdash: **Settings → Integrations → Slack → Connect**
2. Authorize the Lightdash bot in your Slack workspace
3. In any saved dashboard: **Schedule delivery → Select Slack channel → Set frequency**

### Recommended Schedules

| Dashboard | Channel | Frequency | Time |
|:----------|:--------|:----------|:-----|
| CS: Account Health | `#customer-success` | Weekly | Monday 09:00 |
| Finance: Revenue Intelligence | `#finance` | Weekly | Monday 09:00 |
| Sales: Pipeline Overview | `#sales` | Daily | 08:00 |

> **Prerequisite:** Charts must be **saved** in Lightdash before they can be added to scheduled deliveries. Unsaved explores cannot be sent to Slack.

---

## 7. CI/CD & dbt Docs (GitHub Pages)

### dbt Documentation

Automatically deployed to GitHub Pages on every push to `main`:

**URL:** https://farrux05-ai.github.io/b2b-saas-revops-intelligence/

To regenerate locally:

```bash
dbt docs generate
dbt docs serve   # Preview at http://localhost:8080
```

### Manual Docs Update

```bash
dbt docs generate
cp -r target/. docs/        # Copy to GitHub Pages source dir
git add docs/ && git commit -m "docs: refresh dbt docs"
git push origin main
```

---

## 8. Troubleshooting

### MotherDuck: Trial Expired / Connection Failed

```
Invalid Error: Your MotherDuck trial has ended.
```

**Fix:** Log in to [app.motherduck.com](https://app.motherduck.com), select a plan (Free tier available), then generate a new token and update `.env`.

---

### MotherDuck Sync: Binder Error on `stg_hubspot__contacts`

```
Binder Error: Referenced column "linkedin_url" not found in FROM clause
```

**Cause:** `main_staging` was being synced before `raw_data`, so the view couldn't resolve the column in the source table.

**Fix:** Already resolved. `sync_to_motherduck.py` enforces dependency order: `raw_data` → `main_marts` → `main_staging`.

---

### dbt: DuckDB File Lock Error

```
IO Error: Could not set lock on file "revops_intelligence.duckdb"
```

**Cause:** Two processes trying to write to the same DuckDB file simultaneously.

**Fix:** Close any open DuckDB connections (e.g., VS Code SQLTools, a running `dashboard.py`), then re-run `dbt build`. Use `read_only=True` for any non-dbt connections.

---

### Reverse ETL: 401 Unauthorized

```
HTTPError: 401 Client Error: Unauthorized for url: https://api.hubapi.com/...
```

**Cause:** `HUBSPOT_ACCESS_TOKEN` in `.env` is a placeholder (contains `xxxx`) but mock mode wasn't detected.

**Fix:** Already resolved. `reverse_etl_dlt.py` checks `"xxxx" in token` to activate mock mode. If using a real token, verify it has `crm.objects.contacts.write` and `crm.objects.companies.write` scopes in HubSpot.

---

### dbt: `unique_combination_of_columns` Test Failure on `fct_mrr_waterfall`

```
FAIL unique_combination_of_columns_fct_mrr_waterfall_account_id__month_date
```

**Cause:** A subscription change created duplicate `(account_id, month_date)` rows — typically from mid-month plan switches generating two billing events in the same month.

**Investigation:**

```sql
SELECT account_id, month_date, COUNT(*)
FROM main_marts.fct_mrr_waterfall
GROUP BY 1, 2
HAVING COUNT(*) > 1;
```

**Fix:** Review `models/marts/finance/fct_mrr_waterfall.sql` to ensure the deduplication CTE selects the latest record per `(account_id, month_date)`.

---

### Lightdash: New Metric Not Appearing

**Steps:**
1. Verify the metric is defined in the correct `*_schema.yml` under `meta.metrics`
2. Run `dbt parse` locally to check for YAML syntax errors
3. In Lightdash: **Settings → Project → Refresh dbt**
4. Check for metric name collisions (e.g., `total_arr` exists in both `core_schema.yml` and `finance_schema.yml` — use `total_arr_movements` in finance)

---

*For architectural decisions and data model patterns, see [TECHNICAL.md](TECHNICAL.md).*
*For business impact story, see [CASE_STUDY.md](CASE_STUDY.md).*
