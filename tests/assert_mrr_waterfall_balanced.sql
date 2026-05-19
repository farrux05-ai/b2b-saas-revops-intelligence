-- tests/assert_mrr_waterfall_balanced.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}

-- =============================================================================
-- Objective: Ensure the MRR waterfall is internally balanced per month.
-- The waterfall should satisfy:
--   prev_month_mrr + new + expansion - contraction - churn ≈ current_mrr
--
-- Tolerance: $100 per month (rounding/resurrection edge cases)
-- References: fct_mrr_waterfall (replaces legacy fct_mrr)
-- Primary Key: waterfall_id (account_id + month_date surrogate key)
-- =============================================================================

with waterfall as (
    select
        account_id,
        month_date,
        mrr,
        previous_month_mrr,
        mrr_change_amount,
        mrr_movement_type
    from {{ ref('fct_mrr_waterfall') }}
),

-- Classify movements for the global monthly roll-up
monthly as (
    select
        month_date,
        sum(mrr)                                                    as total_mrr,
        sum(case when mrr_movement_type = 'new'        then mrr else 0 end) as new_mrr,
        sum(case when mrr_movement_type = 'expansion'  then mrr_change_amount else 0 end) as expansion_mrr,
        sum(case when mrr_movement_type = 'contraction' then abs(mrr_change_amount) else 0 end) as contraction_mrr,
        sum(case when mrr_movement_type = 'churn'      then previous_month_mrr else 0 end) as churn_mrr
    from waterfall
    group by month_date
),

monthly_with_prev as (
    select
        *,
        lag(total_mrr) over (order by month_date)   as prev_total_mrr
    from monthly
),

-- Find months where the waterfall math doesn't add up
imbalanced as (
    select
        month_date,
        total_mrr,
        prev_total_mrr,
        coalesce(prev_total_mrr, 0) + new_mrr + expansion_mrr
            - contraction_mrr - churn_mrr                           as calculated_mrr,
        abs(
            total_mrr
            - (coalesce(prev_total_mrr, 0) + new_mrr + expansion_mrr - contraction_mrr - churn_mrr)
        )                                                           as mrr_diff
    from monthly_with_prev
    where prev_total_mrr is not null   -- Skip first month (no prior state)
)

select *
from imbalanced
where mrr_diff > 100  -- $100 tolerance for rounding & resurrection edge cases
