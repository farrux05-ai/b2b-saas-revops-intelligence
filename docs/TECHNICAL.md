# Technical Deep-Dive: B2B SaaS RevOps Pipeline

This document explains the **why** behind every architectural decision, with implementation details for other Analytics Engineers.

---

## Table of Contents

1. [Stack Rationale](#stack-rationale)
2. [Data Model Design](#data-model-design)
3. [dbt Layer Strategy](#dbt-layer-strategy)
4. [Performance Optimizations](#performance-optimizations)
5. [Testing Philosophy](#testing-philosophy)
6. [Streamlit Integration](#streamlit-integration)
7. [Common Pitfalls & Solutions](#common-pitfalls--solutions)

---

## Stack Rationale

### Why DuckDB over PostgreSQL/Snowflake?

**Decision:** Use DuckDB for local storage

**Reasoning:**
- **Portability** - Single file (`revops.duckdb`) can be version-controlled (gitignored), backed up, shared
- **Zero ops** - No server setup, no connection pooling, no authentication management
- **Fast OLAP** - Columnar storage, vectorized execution → 10-100x faster than Postgres for aggregations
- **Cost** - Free, no cloud data warehouse bills

**Trade-off:** 
- Limited to single-writer (dbt → Streamlit must coordinate)
- No native replication (solved with file backups)

**When to migrate:** When concurrent users >5 or data >100GB. Migration path: DuckDB → MotherDuck (cloud DuckDB) or Snowflake

---

### Why dbt over Raw SQL Scripts?

**Decision:** Use dbt for transformations instead of Python/pandas or SQL scripts

**Reasoning:**

| Requirement | Raw SQL | dbt |
|-------------|---------|-----|
| **Dependency management** | Manual ORDER BY execution | Automatic DAG resolution |
| **Incrementality** | Custom `WHERE` logic | `{{ is_incremental() }}` macro |
| **Testing** | Separate test scripts | Inline `schema.yml` tests |
| **Documentation** | Separate docs | Auto-generated from YAML |
| **Modularity** | Copy-paste reuse | `{{ ref('model') }}` |

**Example:** Adding a new `stg_zendesk_tickets` model

Raw SQL approach:
```sql
-- Must remember: Run AFTER stg_accounts.sql
-- Must remember: Add to test suite
-- Must remember: Update documentation
CREATE TABLE stg_zendesk_tickets AS 
SELECT ...;
```

dbt approach:
{% raw %}
```sql
-- models/staging/stg_support/stg_zendesk_tickets.sql
{{ config(materialized='view') }}

SELECT 
  ticket_id,
  account_id,  -- dbt validates this exists in stg_accounts
  created_at
FROM {{ source('raw', 'zendesk_tickets') }}
```
{% endraw %}

dbt automatically:
- Runs this AFTER `stg_accounts` (dependency graph)
- Tests `account_id` relationships (if defined in `schema.yml`)
- Documents the model (shows in `dbt docs`)

---

### Why Streamlit over Evidence.dev/Tableau?

**Decision:** Use Streamlit for BI layer

**Comparison:**

| Tool | Strengths | Weaknesses |
|------|-----------|------------|
| **Evidence.dev** | Code-first, Git-native, beautiful defaults | Newer tool, smaller community |
| **Tableau** | Enterprise features, drag-and-drop | Expensive ($70/user/mo), not code-first |
| **Metabase** | Free, easy setup | Limited customization, manual SQL |
| **Streamlit** | Python-native, infinite flexibility | State management needs care |

**Why Streamlit won:**
- **Python Integration** - Direct access to the DuckDB file using Python logic, no separate build step needed.
- **Dynamic Interactivity** - Better support for complex filtering and cross-filtering compared to static SSGs.
- **Custom Components** - Ability to use Plotly, Altair, or custom HTML/JS if needed.
- **Ecosystem** - Massive community and library support for any visual edge-case.

**Example Dashboard code:**
```python
import streamlit as st
import duckdb

# Database connection
conn = duckdb.connect('duckdb/revops.duckdb', read_only=True)

# Query
data = conn.execute("SELECT month, SUM(mrr) FROM fct_revenue GROUP BY 1").df()

# Viz
st.line_chart(data, x='month', y='mrr')
```

This approach allows for a "BI-as-Code" experience while staying within the Python ecosystem.

---

## Data Model Design

### The Account-Centric Star Schema

**Core principle:** Every fact table has `account_id` as a foreign key to `dim_accounts`.

**Why account-centric, not user-centric?**

B2B SaaS decisions happen at the **account level**:
- Pricing/discounts → Account
- Churn risk → Account (one user churning ≠ account churn)
- Expansion opportunities → Account
- Health scores → Account

Even product usage (user-level) is **aggregated to account** for business metrics.

### Dimensional Modeling Principles

**Fact tables = measurements that change**
- `fct_revenue` - MRR per account per month (grain: account × month)
- `fct_pipeline` - Deal progression (grain: one opportunity)
- `fct_product_events` - Aggregated usage (grain: account × day)

**Dimension tables = attributes that change slowly**
- `dim_accounts` - Account properties (name, segment, MRR, health)
- `dim_contacts` - Contact info (name, email, role)
- `dim_dates` - Calendar attributes (day, month, quarter, is_weekend)

### Handling 1:N Relationships

**Problem:** One account has many invoices, many tickets, many contacts.

**Wrong approach:** Join directly in `dim_accounts`
```sql
-- ❌ This creates duplicates!
SELECT a.account_id, a.account_name,
       i.invoice_id, i.amount,
       t.ticket_id, t.status
FROM stg_accounts a
LEFT JOIN stg_invoices i USING (account_id)  -- 5 invoices → 5 rows
LEFT JOIN stg_tickets t USING (account_id)   -- 3 tickets → 15 rows!
```

Result: Account appears 15 times (5 invoices × 3 tickets).

**Correct approach:** Aggregate first, then join
```sql
-- ✅ Aggregate to account level
WITH invoices_agg AS (
  SELECT account_id,
         COUNT(*) AS total_invoices,
         SUM(amount) AS total_revenue
  FROM stg_invoices
  GROUP BY account_id
),
tickets_agg AS (
  SELECT account_id,
         COUNT(*) AS total_tickets,
         AVG(hours_to_first_response) AS avg_response_hours
  FROM stg_tickets
  GROUP BY account_id
)

SELECT a.account_id,
       a.account_name,
       i.total_revenue,
       t.avg_response_hours
FROM stg_accounts a
LEFT JOIN invoices_agg i USING (account_id)
LEFT JOIN tickets_agg t USING (account_id)
```

Result: One row per account, metrics aggregated.

**Implementation:** This pattern is in `models/intermediate/int_accounts.sql`

---

## dbt Layer Strategy

### Three-Layer Architecture

```
staging/ → intermediate/ → marts/
```

**Layer 1: Staging (Views)**

Purpose: Clean, standardize, rename

{% raw %}
```sql
-- models/staging/stg_finance/stg_subscriptions.sql
{{ config(materialized='view') }}

SELECT 
  subscription_id,
  account_id,
  CAST(mrr AS DECIMAL(10,2)) AS mrr,               -- Type casting
  LOWER(status) AS subscription_status,             -- Standardization
  created_at AS subscription_start_date,            -- Renaming
  CASE 
    WHEN status = 'active' AND due_date < CURRENT_DATE 
    THEN TRUE ELSE FALSE 
  END AS is_past_due                                -- Flagging
FROM {{ source('raw', 'stripe_subscriptions') }}
WHERE deleted_at IS NULL                            -- Soft delete filter
```
{% endraw %}

**Why views, not tables?**
- No storage duplication
- Always reflects latest raw data
- Fast dbt compile time (no materialization wait)

**Trade-off:** Downstream models query the view, so complex staging logic slows down marts. Keep staging simple.

---

**Layer 2: Intermediate (Views)**

Purpose: Join sources, apply business logic

{% raw %}
```sql
-- models/intermediate/int_accounts.sql
{{ config(materialized='view') }}

WITH accounts AS (
  SELECT * FROM {{ ref('stg_accounts') }}
),
subscriptions AS (
  SELECT * FROM {{ ref('stg_subscriptions') }}
),
-- Aggregate 1:N relationships
tickets_agg AS (
  SELECT account_id,
         COUNT(*) AS open_tickets
  FROM {{ ref('stg_tickets') }}
  WHERE status IN ('open', 'pending')
  GROUP BY account_id
),
usage_agg AS (
  SELECT account_id,
         MAX(event_timestamp) AS last_active_at
  FROM {{ ref('stg_product_events') }}
  GROUP BY account_id
)

SELECT 
  a.account_id,
  a.account_name,
  s.mrr,
  s.subscription_status,
  s.is_past_due,
  t.open_tickets,
  u.last_active_at,
  DATEDIFF('day', u.last_active_at, CURRENT_DATE) AS days_since_active
FROM accounts a
LEFT JOIN subscriptions s USING (account_id)
LEFT JOIN tickets_agg t USING (account_id)
LEFT JOIN usage_agg u USING (account_id)
```
{% endraw %}

**Why keep this as a view?**
- Marts reference `{{ ref('int_accounts') }}` - if int is a table, marts rebuild is slow
- Views let marts always pull fresh aggregations

---

**Layer 3: Marts (Tables)**

Purpose: Pre-compute expensive metrics for BI tools

```sql
-- models/marts/dim_accounts.sql
{% raw %}
{{ config(
  materialized='table',
  indexes=[{'columns': ['account_id'], 'unique': True}]
) }}
{% endraw %}

SELECT 
  *,
  -- Compute health status (expensive logic)
  CASE
    WHEN subscription_status = 'canceled' THEN 'churned'
    WHEN days_since_active > 30 AND open_tickets = 0 THEN 'inactive'
    WHEN (
      CAST(is_past_due AS INT) +
      CASE WHEN open_tickets > 3 THEN 1 ELSE 0 END +
      CASE WHEN days_since_active > 14 THEN 1 ELSE 0 END
    ) >= 2 THEN 'at_risk'
    ELSE 'healthy'
  END AS health_status
FROM {% raw %}{{ ref('int_accounts') }}{% endraw %}
```

**Why materialize as table?**
- Streamlit queries this during dashboard interactions
- Health logic is complex (multiple CASE statements)
- Table = pre-computed → instant query response

**Trade-off:** Tables are stale between `dbt run` executions. Acceptable for daily refresh cadence.

---

### Incremental Models

For large fact tables, use incremental strategy:

```sql
-- models/marts/fct_product_events.sql
{{ config(
  materialized='incremental',
  unique_key='event_id'
) }}

SELECT 
  event_id,
  account_id,
  event_type,
  event_timestamp
FROM {{ ref('stg_product_events') }}

{% raw %}
{% if is_incremental() %}
  -- Only process new events
  WHERE event_timestamp > (SELECT MAX(event_timestamp) FROM {{ this }})
{% endif %}
```
{% endraw %}

**How it works:**
- First run: Full table build
- Subsequent runs: Only append new rows since last `event_timestamp`
- `unique_key` handles deduplication (if event re-appears, update instead of insert)

**When to use:**
- Tables with >1M rows
- Event streams (product analytics, web logs)
- Daily/hourly refresh cadence

---

## Performance Optimizations

### 1. Indexing Strategy

DuckDB automatically creates indexes on primary keys, but explicit indexes help:

```sql
{{ config(
  materialized='table',
  indexes=[
    {'columns': ['account_id']},
    {'columns': ['created_at']},
    {'columns': ['account_id', 'created_at']}  -- Composite
  ]
) }}
```

**Rule of thumb:**
- Index every foreign key
- Index date columns used in `WHERE` clauses
- Composite index for common join pairs

---

### 2. Query Optimization

**Before:**
```sql
-- ❌ Slow: Subquery in SELECT
SELECT account_id,
       account_name,
       (SELECT COUNT(*) FROM stg_tickets t 
        WHERE t.account_id = a.account_id) AS ticket_count
FROM stg_accounts a
```

**After:**
```sql
-- ✅ Fast: JOIN with aggregation
WITH tickets_agg AS (
  SELECT account_id, COUNT(*) AS ticket_count
  FROM stg_tickets
  GROUP BY account_id
)

SELECT a.account_id,
       a.account_name,
       COALESCE(t.ticket_count, 0) AS ticket_count
FROM stg_accounts a
LEFT JOIN tickets_agg t USING (account_id)
```

**Why faster?**
- Subquery runs once per row (N queries)
- JOIN runs once (1 query)

---

### 3. DuckDB-Specific Tricks

**Use `COPY` for bulk inserts:**
```sql
COPY raw.hubspot_accounts FROM 'data/accounts.csv' 
(HEADER TRUE, DELIMITER ',');
```

10x faster than `INSERT` statements.

**Partition large tables:**
```sql
{{ config(
  materialized='table',
  partition_by='date_trunc(\'month\', event_timestamp)'
) }}
```

Queries with `WHERE event_timestamp` only scan relevant partitions.

---

## Testing Philosophy

### Test Pyramid

```
      /\       3 custom assertions (business logic)
     /  \
    /____\     20 relationship tests (FKs valid)
   /      \
  /________\   144 unique/not_null tests (data quality)
```

**Bottom layer: Schema tests** (80% of tests)
```yaml
# models/staging/stg_sales/schema.yml
models:
  - name: stg_accounts
    columns:
      - name: account_id
        tests:
          - unique
          - not_null
      - name: account_name
        tests:
          - not_null
      - name: created_at
        tests:
          - not_null
```

**Middle layer: Relationship tests**
```yaml
  - name: stg_subscriptions
    columns:
      - name: account_id
        tests:
          - relationships:
              to: ref('stg_accounts')
              field: account_id
```

**Top layer: Custom assertions**
```sql
-- tests/assert_revenue_waterfall_balanced.sql
-- Revenue changes must sum to net MRR change

{% raw %}
WITH revenue_changes AS (
  SELECT 
    SUM(new_mrr + expansion_mrr - churn_mrr - contraction_mrr) AS net_change
  FROM {{ ref('fct_revenue') }}
)

SELECT * FROM revenue_changes
WHERE ABS(net_change) > {{ var('revenue_waterfall_tolerance', 5) }}
```
{% endraw %}

**Why this structure?**
- Schema tests catch 90% of data issues (nulls, duplicates)
- Relationship tests catch broken FKs (orphaned records)
- Custom tests catch business logic bugs (revenue doesn't add up)

---

### Test Execution Strategy

**In development:**
```bash
dbt test --select state:modified+  # Only test changed models
```

**In production:**
```bash
dbt test --store-failures  # Log failures to test_failures schema
```

**Critical path tests** (tagged `critical`):
```yaml
tests:
  - unique:
      tags: ['critical']
```

Run critical tests first:
```bash
dbt test --select tag:critical  # Fail fast
```

---

### Source Freshness Strategy

In B2B SaaS, data latency impacts business decisions differently depending on the domain. Our `dbt source freshness` configuration in `sources.yml` is tailored to these business SLAs rather than using a blanket rule for everything.

**1. Default Catch-All (24h Warn / 48h Error)**
Most raw tables have a global rule: warn after 24 hours, error after 48 hours. This handles typical daily batch syncs where a one-day delay is acceptable, but a two-day delay indicates a systemic pipeline failure.

**2. Product Events (2h Warn)**
Mixpanel product events (`product_events`) have a strict 2-hour warning threshold. Since product usage data is streaming, a 2-hour gap indicates that the ingestion pipeline is stuck. This must be alerted immediately before the delay cascades into downstream aggregations.

**3. CRM & Marketing (6h Warn)**
HubSpot entities like `leads` and `accounts` have a 6-hour warning threshold. Sales representatives rely on fast lead distribution algorithms. If leads are not surfacing in the warehouse for 6 hours, sales outreach SLAs will be breached.

**4. Ignored Entities (null)**
Tables like `dead_letter` (used for capturing ingestion errors) are explicitly set to `freshness: null`. Errors do not occur on a reliable cadence. It is completely normal for a dead letter table to receive no new data for weeks, so setting a freshness threshold here would trigger false positive alerts.

---

## Streamlit Integration

### Connection Setup

**File:** `dashboard.py`

```python
import streamlit as st
import duckdb

@st.cache_resource
def get_connection():
    return duckdb.connect('duckdb/revops_analytics.duckdb', read_only=True)

conn = get_connection()
```

**Why cache_resource?**
- Prevents re-opening the database file on every user interaction or script rerun.
- Drastically improves performance in multi-user environments.

---

### Deployment (Streamlit Cloud)

Streamlit dashboards can be hosted easily on Streamlit Cloud:

1.  **Push to GitHub**: Ensure `dashboard.py` and `requirements.txt` are at the root or correctly linked.
2.  **Connect Repo**: Point Streamlit Cloud to your repository.
3.  **Secrets**: Add secrets for database paths if they are not relative.

Every `git push` → auto-rebuild dashboard.

---

## Common Pitfalls & Solutions

### Pitfall 1: Circular Dependencies

**Error:**
```
Compilation Error: Cycle detected in models: 
  int_accounts → dim_accounts → int_accounts
```

**Cause:** `int_accounts` references `dim_accounts`, which references `int_accounts`

**Solution:** Flatten the dependency
- Move shared logic to a separate `int_base_accounts` model
- Both `int_accounts` and `dim_accounts` reference `int_base_accounts`

---

### Pitfall 2: Snapshot Key Choice

**Wrong:**
```sql
{{ config(
  unique_key='account_name'  -- ❌ Names can change!
) }}
```

**Correct:**
```sql
{{ config(
  unique_key='account_id'  -- ✅ Immutable ID
) }}
```

**Why:** If account name changes, dbt thinks it's a new account → duplicates.

---

### Pitfall 3: DuckDB File Locking

**Error:**
```
IO Error: Could not set lock on file "revops.duckdb": 
Resource temporarily unavailable
```

**Cause:** Streamlit and `dbt run` both trying to access `revops.duckdb` simultaneously.

**Solution:**
Use a read-only connection for Streamlit:
```python
# dashboard.py
conn = duckdb.connect('duckdb/revops_analytics.duckdb', read_only=True)
```
Streamlit only reads, never writes, allowing dbt to run alongside it if needed (though sequential execution is safer).

---

### Pitfall 4: Over-Aggressive Testing

**Wrong:**
```yaml
# Testing every column slows down dbt test
columns:
  - name: account_id
    tests: [unique, not_null]
  - name: account_name
    tests: [not_null]
  - name: industry
    tests: [not_null]
  - name: segment
    tests: [not_null, accepted_values: {values: ['SMB', 'Mid-Market', 'Enterprise']}]
  # ... 20 more columns
```

**Correct:**
```yaml
# Test only critical columns
columns:
  - name: account_id
    tests: [unique, not_null]
  - name: mrr
    tests: [not_null]  # Revenue is critical
  # Skip tests on optional/derived fields
```

**Rule:** Test primary keys, foreign keys, and critical business metrics. Don't test everything.

---

### Pitfall 5: dbt source freshness with DuckDB-Postgres scan

**Error:**
```
Runtime Error in source activities (models/sources.yml)
Binder Error: Catalog "revops_database" does not exist!
```

**Cause:** The architecture uses a custom `postgres_source()` macro (which wraps DuckDB's `postgres_scan()`) to read data directly from Postgres during `dbt run`. However, `dbt source freshness` bypasses custom macros and tries to run a generic `SELECT MAX(_loaded_at)` natively against the catalog defined in `sources.yml`. Because the Postgres database isn't fully `ATTACH`ed to DuckDB internally (it's only read ad-hoc via the macro), DuckDB throws a Catalog error.

**Solution:**
- **Option A (Skip):** Usually in this hybrid OLAP setup, data ingestion pipelines (like Fivetran/Airbyte) have their own freshness monitoring. You can safely skip running `dbt source freshness` and let `dbt run` proceed smoothly.
- **Option B (Architectural Shift):** If dbt-level freshness checks are absolutely critical, you must refactor the architecture. Remove `postgres_scan()` macros and instead mount the Postgres database explicitly using the `attach:` configuration parameter in `profiles.yml` (available in dbt-duckdb 1.8+).

---

## Next Steps

- **[Return to README](../README.md)** for quick start guide
- **[Read Case Study](CASE_STUDY.md)** for business impact story
- **Explore dbt Docs** - Run `dbt docs serve` to see model lineage

---

**Questions?** Open an issue or reach out on [LinkedIn](https://linkedin.com/in/farruxbek-valijonov)