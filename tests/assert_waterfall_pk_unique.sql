-- tests/assert_waterfall_pk_unique.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}

-- =============================================================================
-- Objective: Validate that fct_mrr_waterfall has a unique primary key.
-- Grain: ONE row per account per month (account_id + month_date)
--
-- Duplicate rows indicate a fan-out join (e.g., multiple subscriptions
-- mapping to the same account + month without aggregation).
-- This directly corrupts MRR totals in BI tools.
--
-- Note: waterfall_id is the surrogate key for (account_id + month_date).
-- =============================================================================

select
    waterfall_id,
    account_id,
    month_date,
    count(*) as row_count
from {{ ref('fct_mrr_waterfall') }}
group by waterfall_id, account_id, month_date
having count(*) > 1
