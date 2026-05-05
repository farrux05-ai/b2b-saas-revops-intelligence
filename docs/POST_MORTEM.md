# Project Post Mortem — RevOps dbt Pipeline

This is a living document. Every time we discover a bug, misconfiguration, or design flaw during the review of each layer (Staging → Intermediate → Marts), we record it here.

---

## Layer 0: Configuration & Architecture

### PM-001 · Hardcoded Credentials in profiles.yml
**Severity:** Critical  
**Layer:** Configuration  
**Status:** Fixed

Database credentials (host, user, password, dbname, port) were written directly inside `profiles.yml` as plain text. This file was committed to Git, meaning anyone with repository access could read the production database password.

**Fix:** All credentials moved to `~/.zshrc` as environment variables. `profiles.yml` now reads them via {% raw %}`{{ env_var('DBT_POSTGRES_*') }}`{% endraw %}.

**Rule to remember:** Secrets never go in code. If a value would be embarrassing to see on GitHub, it belongs in an environment variable.

---

### PM-002 · Inconsistent Schema Naming (marts_marts)
**Severity:** High  
**Layer:** Configuration  
**Status:** Fixed

The dbt schema naming convention was inconsistent. The marts layer was being materialized into a schema called `marts_marts` instead of something logical. This caused dashboarding tools (like Streamlit) to fail or require complex joining logic because they were querying schema names that did not match what dbt produced.

**Fix:** `dbt_project.yml` and `profiles.yml` updated so that all three layers use a uniform, readable prefix: `revops_staging`, `revops_int`, `revops_marts`. Dashboard SQL files updated to match.

**Rule to remember:** Schema names should describe the data layer, not repeat the folder structure. Define the naming convention once in `dbt_project.yml` and never override it per model.

---

### PM-003 · dbt source freshness incompatible with postgres_scan() macro
**Severity:** Medium  
**Layer:** Configuration / Architecture  
**Status:** Accepted (documented, not changed)

The project uses a custom `postgres_source()` macro wrapping DuckDB's `postgres_scan()` to read raw Postgres data at query time. This works for `dbt run`. However, `dbt source freshness` does not invoke custom macros — it queries the catalog name defined in `sources.yml` directly. Because Postgres is not `ATTACH`ed to DuckDB as a full catalog, the command fails with `Binder Error: Catalog "revops_database" does not exist`.

**Fix:** Decision made to skip `dbt source freshness` in this hybrid setup. Freshness monitoring is delegated to the ingestion layer (e.g. Fivetran/Airbyte). Detailed in `TECHNICAL.md → Pitfall 5`.

**Rule to remember:** When using a non-standard adapter pattern (like postgres_scan instead of native sources), verify which dbt commands are affected. Not every dbt command is macro-aware.

---

### PM-004 · Non-English comments and descriptions throughout the project
**Severity:** Low  
**Layer:** Configuration / Documentation  
**Status:** Fixed

The majority of YAML descriptions, SQL comments, and documentation files were written in Uzbek. This makes the project inaccessible to any collaborator who does not speak Uzbek and is inconsistent with standard professional practice in data engineering.

**Fix:** All comments, descriptions, and documentation translated to English. Language standard for this project is now English-only.

---

## Layer 1: Staging

### PM-005 · Over-engineered tests — not_null on boolean flag columns
**Severity:** Medium  
**Layer:** Staging / schema YAMLs  
**Status:** Fixed

160+ tests were defined across staging schema files. A significant portion of these were `not_null` tests on columns like `is_amount_null`, `is_owner_null`, `is_close_date_past`. These columns are derived directly from boolean SQL expressions (e.g. `amount IS NULL AS is_amount_null`). A boolean expression in SQL always returns `TRUE` or `FALSE` — it physically cannot produce NULL. Testing `not_null` on them wastes compute on every `dbt test` run and adds noise to test output.

**Fix:** Removed all `not_null` tests from boolean flag columns and derived row-number columns. Kept only: primary keys (`not_null + unique`), foreign keys (`relationships`), and business-critical status fields (`accepted_values`).

**Rule to remember:** Only test what can actually fail. Boolean expressions and `ROW_NUMBER()` outputs cannot be NULL. Testing them is cargo-cult testing — it looks thorough but catches nothing.

---

### PM-006 · Silent bug — email_issue values mismatched between SQL and YAML test
**Severity:** High  
**Layer:** Staging / stg_leads  
**Status:** Fixed

In `stg_leads.sql`, the `email_issue` classification produced two values that did not match what the `accepted_values` test in `marketing_schema.yml` was expecting:

| Column | SQL produced | YAML expected | Result |
|---|---|---|---|
| `email_issue` | `'invalid_form'` | `'invalid_format'` | Always WARN |
| `email_issue` | `'personal_email'` | `'personal_domain'` | Always WARN |

The test was always in a WARN state, but because severity was set to `warn` instead of `error`, the pipeline never failed. The Marketing team would have received wrong email segment labels in dashboards without any alert.

**Fix:** Corrected both string values in `stg_leads.sql` to match the documented accepted values: `'invalid_format'` and `'personal_domain'`.

**Rule to remember:** When you define an `accepted_values` test, the strings in the test must be character-for-character identical to what the SQL produces. Always verify them together. A WARN that is always firing is a bug in disguise.

---

### PM-007 · Truncated comment in stg_contacts.sql
**Severity:** Low  
**Layer:** Staging / stg_contacts  
**Status:** Fixed

A comment on line 22 of `stg_contacts.sql` was cut off mid-sentence:
```sql
-- primary_row_num > 1 = one account one
```
The intent of the `ROW_NUMBER()` window function was unclear to anyone reading the file for the first time.

**Fix:** Comment replaced with a complete, accurate explanation:
```sql
-- Detect accounts with more than one contact marked as primary.
-- primary_row_num > 1 means a duplicate primary contact exists for that account.
```

**Rule to remember:** Incomplete comments are worse than no comments — they suggest the author stopped thinking halfway through. If a comment is worth starting, finish it.

---

### PM-008 · Legacy test syntax — tests: instead of data_tests:
**Severity:** Low  
**Layer:** All staging schema YAMLs  
**Status:** Fixed

All schema YAML files used the old `tests:` key for column-level data tests. Starting in dbt v1.8, this key was deprecated in favour of `data_tests:` to distinguish data quality tests from unit tests. The project is running dbt v1.11.7.

**Fix:** All occurrences of `tests:` under column definitions replaced with `data_tests:` across all 8 schema files using an automated script.

**Rule to remember:** When upgrading dbt versions (or starting a new project), always check the migration guide for deprecated syntax. Running a deprecated key produces a warning on every `dbt run`, adding noise that hides real warnings.

---

## Layer 2: Intermediate

### PM-009 · NULL trap on boolean filter in int_accounts
**Severity:** High  
**Layer:** Intermediate / int_accounts  
**Status:** Fixed

The query filtered subscriptions with `where not is_status_conflict`. Because SQL's three-valued logic evaluates `NOT NULL` as `NULL`, any row where `is_status_conflict` was NULL was being silently dropped from the dataset, causing accounts to lose their active subscriptions.

**Fix:** Changed the filter to `where not coalesce(is_status_conflict, false)` to safely handle NULL flags.

**Rule to remember:** Never use `NOT boolean_column` without a `COALESCE` if the column isn't strictly guaranteed to be non-null. 

---

### PM-010 · Double table scan of stg_product_users causing performance drag
**Severity:** Medium (Performance)  
**Layer:** Intermediate / int_account_health  
**Status:** Fixed

The `stg_product_users` model was read once in the `users` CTE for aggregations, and a second time in the `events` CTE. Unless materialized as a table/view beforehand, dbt runs would execute the staging logic twice, causing unnecessary warehouse reads.

**Fix:** Created a `raw_users` CTE at the top and referenced it in both downstream CTEs (`users` and `events`) to ensure a single logical read.

**Rule to remember:** If you need the same staging model multiple times in the same intermediate query, wrap it in a root CTE and reference that CTE.

---

### PM-011 · Silent loss of campaign_id on soft-deleted campaigns
**Severity:** High  
**Layer:** Intermediate / int_contacts  
**Status:** Fixed

The model joined `first_touch` with `campaigns` to pull campaign metadata. It mapped the final campaign ID using `cmp.id as first_campaign_id`. If a campaign was soft-deleted or missing from the `campaigns` table, `cmp.id` returned NULL, silently wiping out the tracking ID even though `first_touch.campaign_id` had the correct raw ID. 

**Fix:** Used `coalesce(cmp.id, ft.campaign_id) as first_campaign_id` to fall back to the raw tracking ID if the dimension record was missing.

**Rule to remember:** When joining a fact/touch layer to a dimension layer via LEFT JOIN, always coalesce the dimension ID with the fact ID to preserve tracking data when dimension records go missing.

---

### PM-012 · Flawed logic for 'inactive' health status
**Severity:** Medium (Logic)  
**Layer:** Intermediate / int_account_health  
**Status:** Fixed

An account was marked `inactive` if it hadn't been logged into for 30 days AND its `subscription_status = 'active'`. This meant that `trialing` users who abandoned the product were falsely classified as `healthy` instead of `inactive`.

**Fix:** Expanded the logic to `and a.subscription_status in ('active', 'trialing')`.

**Rule to remember:** When defining business logic exclusions based on statuses, always ask "what other statuses exist?" (active vs past_due vs trialing vs cancelled).

---

### PM-013 · Incorrect referential integrity assumptions in schema tests
**Severity:** Medium  
**Layer:** Intermediate / intermediate_schema.yml  
**Status:** Fixed

`int_contacts` applied a `not_null` test on `account_id`, assuming all contacts belong to an account. In reality, standalone contacts (not yet associated with an account) can exist. Furthermore, despite being heavily join-dependent, none of the intermediate models (`int_contacts`, `int_account_health`) had `relationships` tests enforcing that their `account_id` actually existed in the `int_accounts` anchor model.

**Fix:** Removed the strict `not_null` test from `int_contacts.account_id` and added `relationships` tests mapping `account_id` directly to `ref('int_accounts')`.

**Rule to remember:** Test the relationships between your models, not just their staging counterparts. If a model relies on an anchor model, add a relationship test.

---

## Layer 3: Marts

### PM-014 · Attribution Hijacking / Logic Flaw in Pipeline Funnel
**Severity:** Critical  
**Layer:** Marts / fct_pipeline  
**Status:** Fixed

In `fct_pipeline.sql`, Lead campaign attribution was being fetched by mapping the Lead to its Account, and then finding the "Primary Contact" of that Account to use their `first_campaign_name`. If Lead A came from Campaign A, but the Account's primary contact was someone else who came from Campaign X, Lead A's attribution was falsely reported as Campaign X. 

**Fix:** Removed the join to `primary_contacts` for attribution. Instead, joined directly to `stg_campaign_members` (`first_touches`) and `stg_campaigns` using the Lead's own ID. 

**Rule to remember:** Never attribute marketing touches via an Account's primary contact. Attribution should always follow the individual Lead/Contact dimension.

---

### PM-015 · Invalid Relationships Syntax in Marts Schema
**Severity:** Medium  
**Layer:** Marts / marts_schema.yml  
**Status:** Fixed

The `fct_revenue.account_id` column had a relationship test defined with an `arguments:` wrapper inside `relationships:`. This is valid for `accepted_values`, but syntactically invalid for `relationships` tests in dbt, and would cause a catalog validation error.

**Fix:** Removed the `arguments:` wrapper inside the relationships test.

**Rule to remember:** While dbt 1.7+ added the `arguments:` keyword for generic `accepted_values` testing, `relationships` inherently expects `to` and `field` at the root indent.

---

### PM-016 · Translation of Marts models
**Severity:** Low  
**Layer:** Marts / all files  
**Status:** Fixed

Remaining Uzbek comments and descriptions within `dim_accounts.sql`, `fct_revenue.sql`, `fct_pipeline.sql`, and `marts_schema.yml` were translated to English to match project standards.

---

### PM-017 · Test Over-engineering / Cargo-cult testing across Intermediate & Marts
**Severity:** Low (Compute Waste)  
**Layer:** Intermediate & Marts / schema.yml files  
**Status:** Fixed

Similar to PM-005 in the staging layer, numerous `not_null` tests were applied to columns in `intermediate_schema.yml` and `marts_schema.yml` that were mathematically guaranteed to never be null by the SQL engine. Examples include:
- Columns generated via `COALESCE(col, 0)` (`total_contacts`, `open_opportunities`, `mrr`)
- Columns generated via `CASE WHEN ... ELSE 'fallback'` (`health_status`, `funnel_stage`, `account_segment`)
- Metadata columns generated via `CURRENT_TIMESTAMP` (`updated_at`)
- Columns where the model's `WHERE` clause explicitly applies `is not null` (`revenue_month`, `mrr_type` in `fct_revenue`)

Running tests on these columns consumed compute credits on every `dbt test` execution while providing exactly 0% additional confidence in data quality. 

**Fix:** Removed 25+ redundant `not_null` tests across Intermediate and Marts YAML files. Replaced them with descriptions noting they cannot be null natively.

**Rule to remember:** Only test the *data*, do not test the SQL database engine. If your query uses `coalesce()` or an exhaustive `CASE..ELSE`, testing for nulls is cargo-cult testing. Save compute.

---

## Layer 4: Custom Tests (`/tests`)

### PM-018 · Custom Test Out of Sync with Model Logic (`assert_health_status_logic_consistent.sql`)
**Severity:** Medium  
**Layer:** Tests / assert_health_status_logic_consistent  
**Status:** Fixed

During the intermediate layer review, we updated `int_account_health` to use dynamic thresholds via `dbt_project.yml` variables rather than hardcoded rules (e.g., `avg_response_hours > {% raw %}{{ var('at_risk_response_hours') }}{% endraw %}`). However, the related custom test `assert_health_status_logic_consistent.sql` was still strictly checking for `urgent_open_tickets` and hardcoded `30 days`, ignoring the new risk flags. This mismatch would either cause false positives or fail to catch actual violations.

**Fix:** Updated the custom test's `UNION ALL` statements to match the exact `var()` definitions and extended risk rules used by the model. 

**Rule to remember:** When refactoring business logic or migrating hardcoded thresholds into data variables, always check if any `.sql` or `.yml` tests explicitly assert that logic and update them synchronously.

---

### PM-019 · Cargo-Cult Custom Testing (`assert_no_duplicate_emails_in_staging.sql` & `assert_one_row_per_account_in_int.sql`)
**Severity:** Low (Compute Waste / Redundancy)  
**Layer:** Tests  
**Status:** Fixed

Found two `.sql` tests that were entirely redundant:
1. `assert_one_row_per_account_in_int.sql` explicitly grouped by `account_id` and had `HAVING COUNT(*) > 1`. This is literally the exact same SQL that the generic `unique` test handles when applied to `int_accounts.account_id` (which was already configured).
2. `assert_no_duplicate_emails_in_staging.sql` checked for duplicates where `email_row_num = 1`. Mathematically, `ROW_NUMBER() OVER(PARTITION BY email)` guarantees that all rows where `email_row_num = 1` are unique. Testing this is equivalent to testing if `1 = 1`.

**Fix:** Deleted both redundant test files to keep the test suite lean, deterministic, and fast. Translated comments in remaining valid Custom tests (`assert_revenue_waterfall_balanced.sql` and `assert_mrr_positive_and_arr_consistent.sql`) to English.

**Rule to remember:** Never write a custom `.sql` test for logic that a standard generic `unique`, `not_null`, or `accepted_values` test natively handles. Also, do not test mathematical window function axioms.

---

## Layer 5: Snapshots (`/snapshots`)

### PM-020 · False Delta Bloat in SCD Type 2 History
**Severity:** High (Database Bloat / Data Accuracy)  
**Layer:** Snapshots / all snapshots  
**Status:** Fixed

Both `snap_dim_accounts.sql` and `snap_fct_pipeline.sql` were configured with `strategy='timestamp'` pointing to `updated_at`. However, in the underlying Marts models, `updated_at` was hardcoded as `current_timestamp`. 

**Impact:** Because the timestamp updated every second/minute, dbt snapshot erroneously detected a "change" for every single row in the database every time it ran. This would have caused the snapshot tables to grow exponentially and rendered historical comparison useless (since every record would have a lifespan of only 1-2 hours).

**Fix:** Switched from `strategy='timestamp'` to `strategy='check'` with `check_cols='all'`. This ensures a new historical record is only created if the actual data values change, regardless of the metadata timestamp.

**Rule to remember:** Never use a `timestamp` strategy on a column that is generated via `current_timestamp` or any non-deterministic function in SQL. If you don't have a reliable source-system update timestamp, use `strategy='check'`. Use `check_cols='all'` for wide dimension tables to capture any attribute change.

---

## Layer 6: Governance & Contracts

### PM-021 · Over-engineering with dbt Model Contracts
**Severity:** Low (Process/Efficiency)  
**Layer:** Marts / Governance  
**Status:** Resolved (Reverted)

We initially implemented dbt Model Contracts (`contract: {enforced: true}`) for the `dim_accounts` model. This was intended to provide schema enforcement and prevent breaking changes for downstream consumers. 

**The "Over-engineering" Trap:** For this specific project context (high iteration speed, single developer, local DuckDB environment), Model Contracts proved to be over-engineering. Every minor change in the SQL (e.g., adding a column or changing a cast) required a corresponding manual update to the YAML file to specify the `data_type`. This added significant administrative overhead without providing proportional value, as the project lacks external consumers who require such strict schema guarantees.

**When to use Contracts:** 
- High-stakes production environments with multiple downstream teams (e.g., separate BI, Machine Learning, or Product teams).
- Large-scale projects where schema drift must be caught *before* the model is materialized in the database.
- When using adapters that support database-level constraints (Postgres, Snowflake) and where performance-critical constraints are needed.

**When they are Over-engineering:**
- Local development/prototyping where schemas are still evolving daily.
- Small-scale pipelines where standard dbt tests (`unique`, `not_null`, `accepted_values`) provide sufficient data quality coverage.
- When the cost of manually maintaininig YAML `data_type` mappings outweighs the risk of a schema change.

**Fix:** Reverted the `dim_accounts` contract and specifying `data_type` in `marts_schema.yml`. Standard Data Tests (`not_null`, `unique`, `accepted_values`) are maintained as they provide sufficient validation for current business needs.

**Rule to remember:** "Simplicity is the ultimate sophistication." Do not implement complex governance features like Data Contracts until the project reaches a level of maturity or consumer scale that genuinely requires them. Testing business logic with `.sql` tests is often more important than enforcing strict schema types in the early stages.
