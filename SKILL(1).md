---
name: dbt-snowflake-expert
description: Expert in dbt (data build tool) with Snowflake data warehouse optimization. Use this skill whenever the user mentions dbt, Snowflake, data transformations, incremental models, dbt tests, macros, snapshots, dbt packages, query optimization, warehouse sizing, clustering keys, materialization strategies, or asks about modeling patterns, performance tuning, cost optimization, or debugging dbt runs. Also trigger for questions about dimensional modeling in dbt, semantic/metrics layer, dbt mesh, or CI/CD for dbt projects. Even casual mentions like "my dbt project" or "this model is slow" should trigger this skill.
---

# dbt + Snowflake Expert

Comprehensive guidance for building production-grade data transformations with dbt on Snowflake.

## Core Philosophy

### 1. **Modularity Over Monoliths**
- One model = one business entity
- Staging → Intermediate → Marts
- Reusable logic in macros

### 2. **Performance by Design**
- Incremental where possible
- Clustering for large tables
- Warehouse sizing based on query patterns

### 3. **Test Everything**
- Schema tests on every model
- Data tests for business logic
- Freshness checks on sources

---

## Project Structure

### Recommended Layout

```
dbt_project/
├── models/
│   ├── staging/          # Raw source cleaning
│   │   ├── stripe/
│   │   ├── salesforce/
│   │   └── _sources.yml
│   ├── intermediate/     # Business logic transforms
│   │   ├── customers/
│   │   ├── subscriptions/
│   │   └── _intermediate.yml
│   ├── marts/           # Final business entities
│   │   ├── finance/
│   │   │   ├── fct_revenue.sql
│   │   │   ├── dim_customers.sql
│   │   │   └── _finance.yml
│   │   └── product/
│   └── metrics/         # dbt Semantic Layer
├── macros/
│   ├── generate_schema_name.sql
│   ├── custom_tests/
│   └── helpers/
├── tests/
│   └── generic/
├── snapshots/
├── seeds/
├── analyses/
└── dbt_project.yml
```

---

## Materialization Strategies

### 1. **Views**
**Use for**: Lightweight transformations, no performance issues.

```sql
{{ config(
    materialized='view'
) }}

SELECT
  customer_id,
  email,
  LOWER(TRIM(email)) AS email_normalized
FROM {{ source('stripe', 'customers') }}
```

**Pros**: Always fresh, no storage cost
**Cons**: Slow if downstream queries are complex

---

### 2. **Tables**
**Use for**: Final marts, frequently queried models.

```sql
{{ config(
    materialized='table',
    cluster_by=['customer_id', 'created_date']
) }}

SELECT
  customer_id,
  created_date,
  total_revenue
FROM {{ ref('intermediate_revenue') }}
```

**Pros**: Fast queries
**Cons**: Storage cost, rebuild overhead

---

### 3. **Incremental Models**
**Use for**: Large event tables, append-only data.

```sql
{{ config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    cluster_by=['event_date']
) }}

SELECT
  event_id,
  user_id,
  event_name,
  event_timestamp::date AS event_date,
  properties
FROM {{ source('segment', 'events') }}

{% if is_incremental() %}
  WHERE event_timestamp > (SELECT MAX(event_timestamp) FROM {{ this }})
{% endif %}
```

**Critical**: Always include `is_incremental()` filter!

---

### 4. **Incremental Strategies**

#### **A. Merge (Most Common)**
Updates existing rows, inserts new ones.

```sql
{{ config(
    materialized='incremental',
    unique_key='subscription_id',
    incremental_strategy='merge'
) }}

SELECT
  subscription_id,
  customer_id,
  status,
  mrr,
  updated_at
FROM {{ source('billing', 'subscriptions') }}

{% if is_incremental() %}
  WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

**When to use**: Type 1 SCD (latest state only), data can change.

---

#### **B. Append (Fastest)**
Only inserts, never updates.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='append'
) }}

SELECT
  event_id,
  user_id,
  event_timestamp
FROM {{ source('events', 'clicks') }}

{% if is_incremental() %}
  WHERE event_timestamp > (SELECT MAX(event_timestamp) FROM {{ this }})
{% endif %}
```

**When to use**: Immutable event data, logs.

---

#### **C. Delete+Insert**
Deletes partition, then inserts.

```sql
{{ config(
    materialized='incremental',
    unique_key='date',
    incremental_strategy='delete+insert'
) }}

SELECT
  date,
  SUM(revenue) AS total_revenue
FROM {{ ref('transactions') }}
GROUP BY 1

{% if is_incremental() %}
  WHERE date >= DATEADD('day', -7, CURRENT_DATE)
{% endif %}
```

**When to use**: Daily aggregations that need full recalc.

---

### 5. **Ephemeral**
**Use for**: Intermediate CTEs, no storage.

```sql
{{ config(
    materialized='ephemeral'
) }}

SELECT
  customer_id,
  SUM(amount) AS total_spent
FROM {{ ref('transactions') }}
GROUP BY 1
```

**Pros**: No table created, DRY code
**Cons**: Inlined into every downstream query (can be slow)

---

## Snowflake Optimization

### 1. **Clustering Keys**

**When to cluster**:
- Table > 1TB
- Queries filter on specific columns
- Query performance issues

```sql
{{ config(
    materialized='table',
    cluster_by=['event_date', 'user_id']
) }}
```

**Best practices**:
- Use 1-4 columns max
- High-cardinality first (dates, IDs)
- Match filter patterns

**Check clustering**:
```sql
SELECT SYSTEM$CLUSTERING_INFORMATION('table_name', '(event_date, user_id)')
```

---

### 2. **Warehouse Sizing**

**Strategy**:
```yaml
# profiles.yml
dbt_project:
  outputs:
    dev:
      warehouse: dev_wh_xs
    prod:
      warehouse: prod_wh_large
```

**Guidelines**:
- XS/S: Development, tests
- M: Regular transformations
- L/XL: Large incremental loads, full refreshes
- 2XL+: Heavy aggregations, large joins

**Cost optimization**:
```sql
-- Use smaller warehouses for more models
{{ config(
    snowflake_warehouse='transforming_xs'
) }}
```

---

### 3. **Query Optimization**

#### **Avoid SELECT \***
```sql
-- Bad
SELECT * FROM {{ ref('large_table') }}

-- Good
SELECT
  customer_id,
  email,
  created_at
FROM {{ ref('large_table') }}
```

#### **Use CTEs for Readability**
```sql
WITH active_customers AS (
  SELECT customer_id
  FROM {{ ref('customers') }}
  WHERE status = 'active'
),
recent_orders AS (
  SELECT
    customer_id,
    order_date
  FROM {{ ref('orders') }}
  WHERE order_date >= DATEADD('day', -30, CURRENT_DATE)
)
SELECT
  ac.customer_id,
  COUNT(ro.order_date) AS order_count
FROM active_customers ac
LEFT JOIN recent_orders ro USING (customer_id)
GROUP BY 1
```

#### **Filter Early**
```sql
-- Push filters into CTEs
WITH filtered_events AS (
  SELECT *
  FROM {{ ref('events') }}
  WHERE event_date >= '2024-01-01'  -- Filter ASAP
)
```

#### **Use QUALIFY for Window Functions**
```sql
-- Instead of subquery
SELECT
  customer_id,
  order_date,
  ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn
FROM {{ ref('orders') }}
QUALIFY rn = 1  -- Snowflake-specific!
```

---

## Testing

### 1. **Schema Tests** (in `.yml`)

```yaml
version: 2

models:
  - name: fct_revenue
    description: Daily revenue by customer
    columns:
      - name: customer_id
        description: Unique customer identifier
        tests:
          - not_null
          - unique
      - name: revenue_date
        tests:
          - not_null
      - name: total_revenue
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              inclusive: true
```

### 2. **Relationships**
```yaml
- name: subscription_id
  tests:
    - relationships:
        to: ref('dim_subscriptions')
        field: subscription_id
```

### 3. **Custom Tests**
```sql
-- tests/assert_revenue_positive.sql
SELECT
  customer_id,
  revenue_date,
  total_revenue
FROM {{ ref('fct_revenue') }}
WHERE total_revenue < 0
```

### 4. **Data Tests with dbt_utils**
```yaml
- name: mrr
  tests:
    - dbt_utils.not_null_proportion:
        at_least: 0.95
    - dbt_utils.recency:
        datepart: day
        field: updated_at
        interval: 1
```

---

## Snapshots (Type 2 SCD)

**Use for**: Tracking changes over time.

```sql
-- snapshots/subscription_snapshot.sql
{% snapshot subscription_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='subscription_id',
      strategy='timestamp',
      updated_at='updated_at',
      invalidate_hard_deletes=True
    )
}}

SELECT
  subscription_id,
  customer_id,
  status,
  mrr,
  updated_at
FROM {{ source('billing', 'subscriptions') }}

{% endsnapshot %}
```

**Run**: `dbt snapshot`

**Result**:
```
| subscription_id | mrr  | dbt_valid_from | dbt_valid_to |
|-----------------|------|----------------|--------------|
| sub_123         | 100  | 2024-01-01     | 2024-02-01   |
| sub_123         | 150  | 2024-02-01     | NULL         |
```

---

## Macros

### 1. **Reusable Logic**

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name) %}
  ({{ column_name }} / 100.0)::decimal(10,2)
{% endmacro %}
```

**Usage**:
```sql
SELECT
  order_id,
  {{ cents_to_dollars('amount_cents') }} AS amount_dollars
FROM {{ ref('orders') }}
```

---

### 2. **Generate Schema Name**

```sql
-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

**Use in model**:
```sql
{{ config(
    schema='finance'
) }}
-- Creates schema: finance (not dev_finance)
```

---

### 3. **Custom Test**

```sql
-- macros/test_valid_email.sql
{% test valid_email(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} NOT LIKE '%_@__%.__%'
  OR {{ column_name }} IS NULL

{% endtest %}
```

**Usage**:
```yaml
columns:
  - name: email
    tests:
      - valid_email
```

---

## dbt Packages

### Essential Packages

```yaml
# packages.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
  - package: calogica/dbt_expectations
    version: 0.10.0
  - package: dbt-labs/metrics
    version: 1.6.0
```

**Install**: `dbt deps`

---

### Useful Macros

```sql
-- dbt_utils.surrogate_key
SELECT
  {{ dbt_utils.surrogate_key(['customer_id', 'order_id']) }} AS order_key
FROM orders

-- dbt_utils.generate_series
{{ dbt_utils.generate_series(1, 12) }}

-- dbt_utils.pivot
{{ dbt_utils.pivot(
    column='product_name',
    values=['ProductA', 'ProductB'],
    agg='sum',
    then_value='revenue'
) }}
```

---

## Debugging

### 1. **Compiled SQL**

```bash
dbt compile --select fct_revenue
cat target/compiled/dbt_project/models/marts/finance/fct_revenue.sql
```

### 2. **Log Output**

```bash
dbt run --select fct_revenue --debug
```

### 3. **Query History**

```sql
-- Check Snowflake query history
SELECT
  query_text,
  execution_time,
  warehouse_size,
  bytes_scanned
FROM snowflake.account_usage.query_history
WHERE query_text ILIKE '%fct_revenue%'
ORDER BY start_time DESC
LIMIT 10
```

### 4. **Model Timing**

```bash
dbt run --select fct_revenue --log-format json > run.log
cat run.log | jq 'select(.info.level == "info") | .info.msg'
```

---

## CI/CD Pipeline

### GitHub Actions Example

```yaml
name: dbt CI
on:
  pull_request:
    branches: [main]

jobs:
  dbt-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: dbt deps
        run: dbt deps
      - name: dbt run (modified models)
        run: dbt run --select state:modified+ --defer --state ./prod-manifest/
      - name: dbt test
        run: dbt test --select state:modified+
```

---

## Performance Checklist

### Before Committing Code

- [ ] Incremental models have `is_incremental()` filter
- [ ] Large tables (>100M rows) are clustered
- [ ] All models have tests
- [ ] No `SELECT *` unless necessary
- [ ] CTEs are used for readability
- [ ] Expensive transformations use appropriate warehouse size
- [ ] Snapshots for slowly changing dimensions
- [ ] Documentation in `.yml` files

---

## Best Practices Summary

1. **Staging Layer**: Clean raw sources only (rename, cast, dedupe)
2. **Intermediate Layer**: Business logic, joins, filters
3. **Marts Layer**: Final aggregations, wide tables
4. **Test Everything**: Schema + data tests
5. **Use Macros**: DRY principle
6. **Document**: `.yml` files for every model
7. **Incremental by Default**: For large tables
8. **Monitor Costs**: Snowflake query history
9. **Version Control**: Git + PR reviews
10. **CI/CD**: Automated testing on PRs

---

## When to Use This Skill

Claude should reference this skill when:
- Writing or reviewing dbt models
- Debugging slow queries or models
- Optimizing Snowflake costs
- Designing data transformation pipelines
- Setting up tests or snapshots
- Creating macros or custom tests
- Configuring materialization strategies
- Planning dbt project structure

---

## References

For business metrics logic, see: `revops-metrics-expert` skill
For dimensional modeling, see: `data-modeling-architect` skill
