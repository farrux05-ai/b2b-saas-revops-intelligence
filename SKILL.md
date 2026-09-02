---
name: sentinelguard-revops-standard
description: The ultimate enterprise standard for B2B SaaS RevOps data architecture, dbt modeling, SQL CTE standards, and identity resolution.
---

# RevOps Intelligence Engine RevOps Standard

## 1. Naming & Directory Structure
- **Staging**: `stg_[source]__[entity].sql` (Double underscore between source system and entity name).
  - Location: `models/staging/[source]/`
- **Intermediate**: `int_[entity]_[verb].sql` (Must end with descriptive action verb: `_joined`, `_aggregated`, `_integrated`, `_scored`).
  - Location: `models/intermediate/[domain]/`
- **Marts**: `dim_[entity].sql` (One Big Table / Conformed Dimension) and `fct_[entity].sql` (Historical State / Event Fact).
  - Location: `models/marts/[domain]/`
- **Utilities**: Non-business infrastructure models in `models/utilities/` (e.g., `dim_dates.sql`).

---

## 2. Identity Resolution & Master Spine Rule
- **Rule**: NEVER use `LEFT JOIN` on a single CRM or billing table as the identity spine.
- **Method**: Use `UNION ALL` across all raw identity providers (App Workspaces, HubSpot Leads, Stripe Customers) to create a unified identity spine.
- **Rationale**: Prevents "PLG Leakage" — ensures leads and product users are tracked in analytics even before they convert or appear in the CRM.

---

## 3. Intermediate 3-Stage Hierarchy
1. **Identity Stage (`_joined`)**: Join raw staging tables to stitch global surrogate keys (e.g., `account_id`, `user_id`).
2. **Domain Stage (`_aggregated`)**: Aggregate metrics within distinct functional domains (Sales pipeline, Stripe billing, Product usage).
3. **Integration Stage (`_integrated` / `_scored`)**: Merge domain metrics onto the master identity spine and apply ML/heuristic scoring (Account Health, Churn Risk).

---

## 4. Finance & MRR Waterfall Standard
- **Rule**: No `now()` or current-state column logic for historical movements.
- **Method**: Use a **Date Spine** (`dim_dates`) to generate deterministic daily/monthly point-in-time snapshots of subscription states.
- **MRR Movements**: Categorize all monthly balance deltas into explicit buckets:
  - `New`: First time active subscription.
  - `Expansion`: MRR increased vs previous period.
  - `Contraction`: MRR decreased (non-zero) vs previous period.
  - `Churn`: Subscription cancelled / MRR dropped to 0.
  - `Reactivation`: Subscription restarted after churn.

---

## 5. SQL Syntax & CTE Formatting Rules
- **Structure**: All models must use CTE-first syntax: `source_data` -> `transformation_ctes` -> `final`.
- **Keywords**: Lowercase for all SQL keywords (`select`, `from`, `where`, `left join`, `group by`, `order by`).
- **Explicit Selects**: No `SELECT *` in final output CTEs.
- **Lineage**: Always use dbt `{{ ref(...) }}` and `{{ source(...) }}` macros.

---

## 6. Layered Testing Philosophy
- **Staging Layer**: Verify source contract only. `unique` and `not_null` on primary keys. `accepted_values` only on source-managed status enums.
- **Intermediate Layer**: Test foreign keys, surrogate key uniqueness, and business logic boundaries.
- **Marts Layer**: Test business reliability and dimension uniqueness (`dim_` primary keys, `dbt_expectations` row counts).
- **Rule**: Do not duplicate tests across layers.
