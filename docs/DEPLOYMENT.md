# Deployment Runbook: RevOps Intelligence Engine

This document covers end-to-end deployment of all pipeline components: environment setup, Snowflake warehouse configuration, BI layer, and orchestration.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Snowflake Warehouse Configuration](#2-snowflake-warehouse-configuration)
3. [Pipeline Execution](#3-pipeline-execution)
4. [Lightdash Setup](#4-lightdash-setup)
5. [Dagster Scheduling](#5-dagster-scheduling)
6. [Slack Bot Integration](#6-slack-bot-integration)
7. [CI/CD & dbt Docs (GitHub Pages)](#7-cicd--dbt-docs-github-pages)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Environment Setup

### Fast Python Environment with `uv`

```bash
# Create venv and activate
uv venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies using uv
uv pip install -r requirements.txt
```

### Environment Variables

Copy the template and fill in your credentials:

```bash
cp .env.example .env
```

Required variables in `.env`:

```env
# Snowflake Credentials
SNOWFLAKE_ACCOUNT=your_snowflake_account_identifier  # e.g. xy12345.us-east-1
SNOWFLAKE_USER=your_snowflake_username
SNOWFLAKE_PASSWORD=your_snowflake_password
SNOWFLAKE_ROLE=TRANSFORMER
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=REVOPS_INTELLIGENCE

# HubSpot Reverse ETL
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxx-xxxx-xxxx-xxxx

# Slack Observability Alerts (optional)
SLACK_WEBHOOK=https://hooks.slack.com/services/xxx/yyy/zzz
```

> **Mock Mode:** `reverse_etl_dlt.py` automatically detects placeholder tokens (containing `"xxxx"`) and skips live API calls safely.

### dbt Profile

`profiles.yml` is pre-configured to use **Snowflake** as the default target:

```yaml
revops_intelligence_engine:
  target: snowflake
  outputs:
    snowflake:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'TRANSFORMER') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH') }}"
      database: "{{ env_var('SNOWFLAKE_DATABASE', 'REVOPS_INTELLIGENCE') }}"
      schema: MARTS
      threads: 8
```

---

## 2. Snowflake Warehouse Configuration

### Initial Database Setup in Snowflake

Run the following DDL in Snowflake Web UI or SnowSQL to set up roles and database schemas:

```sql
-- 1. Create Role & Warehouse
CREATE ROLE IF NOT EXISTS TRANSFORMER;
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH WITH WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

-- 2. Create Database
CREATE DATABASE IF NOT EXISTS REVOPS_INTELLIGENCE;

-- 3. Create Schemas
CREATE SCHEMA IF NOT EXISTS REVOPS_INTELLIGENCE.RAW_DATA;
CREATE SCHEMA IF NOT EXISTS REVOPS_INTELLIGENCE.STAGING;
CREATE SCHEMA IF NOT EXISTS REVOPS_INTELLIGENCE.INTERMEDIATE;
CREATE SCHEMA IF NOT EXISTS REVOPS_INTELLIGENCE.MARTS;
CREATE SCHEMA IF NOT EXISTS REVOPS_INTELLIGENCE.ELEMENTARY;

-- 4. Grant Permissions to TRANSFORMER role
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE TRANSFORMER;
GRANT ALL ON DATABASE REVOPS_INTELLIGENCE TO ROLE TRANSFORMER;
GRANT ALL ON ALL SCHEMAS IN DATABASE REVOPS_INTELLIGENCE TO ROLE TRANSFORMER;
```

---

## 3. Pipeline Execution

### Step 1: Generate Mock Data & Ingest into Snowflake (dlt)

```bash
# 1. Generate mock JSON data
python scripts/generate_mock_data.py

# 2. Ingest raw data into Snowflake RAW_DATA schema
python ingestion/stackflow_pipeline.py
```

### Step 2: Run dbt Transformation & Quality Tests

```bash
# Build all models, seeds, snapshots, and tests on Snowflake
dbt build --target snowflake --store-failures

# Or build individual layers:
dbt build --select staging --target snowflake
dbt build --select intermediate --target snowflake
dbt build --select marts --target snowflake

# Source freshness check
dbt source freshness --target snowflake
```

### Step 3: Run Elementary Observability & Slack Alerts

```bash
# Generate Elementary HTML observability report from Snowflake metadata
edr report --target snowflake

# Send test failure alerts to Slack
edr send-report --slack-token $SLACK_TOKEN --slack-channel data-alerts
```

### Step 4: Reverse ETL to HubSpot

```bash
# Dry run preview (no API calls made)
python scripts/reverse_etl_dlt.py --dry-run

# Live sync from Snowflake MARTS to HubSpot API
python scripts/reverse_etl_dlt.py
```

---

## 4. Lightdash Setup

### Connect Lightdash to Snowflake

Lightdash connects directly to Snowflake using the dbt semantic layer:

1. In Lightdash, go to **Settings → Connections → Add project**
2. Select **Snowflake** as warehouse
3. Fill in connection details:
   - **Account:** your Snowflake account identifier
   - **User / Password:** your Snowflake credentials
   - **Warehouse:** `COMPUTE_WH`
   - **Database:** `REVOPS_INTELLIGENCE`
   - **Schema:** `MARTS`
4. Connect your **GitHub repository**
5. Set **dbt project path** to `/` (root of this repository)

### Semantic Layer Reference

Metrics and dimensions are defined in code in these files:

| File | Models | Key Metrics |
|:-----|:-------|:-----------|
| `models/marts/core/core_schema.yml` | `dim_accounts`, `dim_users`, `dim_dates` | `total_arr`, `total_mrr` |
| `models/marts/customer_success/cs_schema.yml` | `fct_accounts_health` | `at_risk_accounts`, `total_mrr_at_risk` |
| `models/marts/finance/finance_schema.yml` | `fct_mrr_waterfall`, `fct_arr_movements` | `total_arr_movements`, `total_churn_mrr` |
| `models/marts/sales/sales_schema.yml` | `fct_pipeline` | `total_pipeline_value`, `weighted_pipeline_value` |
| `models/marts/marketing/marketing_schema.yml` | `fct_lead_funnel`, `fct_attribution` | `total_leads`, `conversion_rate` |

---

## 5. Dagster Scheduling

### Running Dagster UI

```bash
dagster dev -f dagster_pipeline.py
# Open http://localhost:3000
```

### Jobs Available

| Job | Selection | Description |
|:----|:----------|:------------|
| `revops_full_pipeline_job` | `AssetSelection.all()` | Full 4-step pipeline: Ingestion → dbt Snowflake → Reverse ETL → Observability |
| `revops_ingestion_only_job` | `ingestion_dlt` | Ingestion only into Snowflake `RAW_DATA` |
| `revops_transform_only_job` | `revops_dbt_assets` + `dlt_reverse_etl` | dbt build on Snowflake + Reverse ETL (skips ingestion) |

### Daily Schedule

Configured in `dagster_pipeline.py` to execute daily at **07:00 UTC**:

```python
revops_daily_schedule = ScheduleDefinition(
    name="revops_daily_07_utc",
    job=revops_full_pipeline_job,
    cron_schedule="0 7 * * *",
    execution_timezone="UTC",
)
```

---

## 6. Slack Bot Integration

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

---

## 7. CI/CD & dbt Docs (GitHub Pages)

### dbt Documentation

Deployed automatically to GitHub Pages on every push to `main`:

**URL:** https://farrux05-ai.github.io/b2b-saas-revops-intelligence/

To generate and preview locally:

```bash
dbt docs generate --target snowflake
dbt docs serve   # Preview at http://localhost:8080
```

---

## 8. Troubleshooting

### Snowflake: Invalid Credentials / Connection Failed

```
250001 (08001): Failed to connect to DB: ... Incorrect username or password
```

**Fix:** Verify `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and `SNOWFLAKE_PASSWORD` in `.env`. Ensure your account string uses lowercase/dashes without `https://` prefix (e.g. `xy12345.us-east-1`).

---

### Reverse ETL: 401 Unauthorized

```
HTTPError: 401 Client Error: Unauthorized for url: https://api.hubapi.com/...
```

**Fix:** `reverse_etl_dlt.py` checks `"xxxx" in token` to activate mock mode safely. If using a real token, ensure it has `crm.objects.contacts.write` and `crm.objects.companies.write` scopes in HubSpot.

---

### dbt: `unique_combination_of_columns` Test Failure on `fct_mrr_waterfall`

```
FAIL unique_combination_of_columns_fct_mrr_waterfall_account_id__month_date
```

**Fix:** Inspect failing rows saved in Snowflake:
```sql
SELECT * FROM REVOPS_INTELLIGENCE.MARTS_DBT_TEST__AUDIT.UNIQUE_COMBINATION_OF_COLUMNS_FCT_MRR_WATERFALL_ACCOUNT_ID__MONTH_DATE;
```

---

*For architectural decisions and data model patterns, see [TECHNICAL.md](TECHNICAL.md).*
*For business impact story, see [CASE_STUDY.md](CASE_STUDY.md).*
