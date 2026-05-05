-- tests/assert_revenue_waterfall_balanced.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}

-- Objective: Ensure the MRR waterfall is balanced
-- For each month: prev_mrr + new + expansion - contraction - churn
-- = current_mrr (with a permitted tolerance)

with monthly as (
    select
        date_month,
        sum(mrr) as total_mrr,
        sum(case when mrr_type = 'new' then mrr else 0 end) as new_mrr,
        sum(case when mrr_type = 'expansion' then mrr_change else 0 end) as expansion_mrr,
        sum(case when mrr_type = 'contraction' then abs(mrr_change) else 0 end) as contraction_mrr,
        sum(case when mrr_type = 'churn' then prev_month_mrr else 0 end) as churn_mrr
    from {{ ref('fct_mrr') }}
    group by 1
),

monthly_with_prev as (
    select
        date_month,
        total_mrr,
        new_mrr,
        expansion_mrr,
        contraction_mrr,
        churn_mrr,
        lag(total_mrr) over (order by date_month) as prev_mrr
    from monthly
),

imbalanced as (
    select
        date_month,
        total_mrr,
        prev_mrr,
        coalesce(prev_mrr, 0)
            + coalesce(new_mrr, 0)
            + coalesce(expansion_mrr, 0)
            - coalesce(contraction_mrr, 0)
            - coalesce(churn_mrr, 0)                     as calculated_mrr,
        abs(
            total_mrr - (
                coalesce(prev_mrr, 0)
                + coalesce(new_mrr, 0)
                + coalesce(expansion_mrr, 0)
                - coalesce(contraction_mrr, 0)
                - coalesce(churn_mrr, 0)
            )
        )                                                   as mrr_diff
    from monthly_with_prev
    where prev_mrr is not null
)

select *
from imbalanced
where mrr_diff > 100 -- Low tolerance for professional finance tracking
