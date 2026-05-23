{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_unit_economics
-- LAYER: Marts / Finance
--
-- PURPOSE: LTV (Lifetime Value) estimates per account segment.
-- NOTE: CAC is not available (no marketing spend data in pipeline).
--       LTV is estimated using: Average MRR / Monthly Churn Rate.
--
-- FORMULA:
--   Monthly Churn Rate = Churned MRR this month / Starting MRR
--   LTV = Avg MRR per Active Account / Monthly Churn Rate
--   LTV:ARR Ratio = LTV / (Avg MRR × 12)
-- =============================================================================

with cohorts as (
    select * from {{ ref('fct_retention_cohorts') }}
),

subscriptions as (
    select * from {{ ref('fct_subscriptions') }}
),

-- Account segment from dim_accounts
accounts as (
    select account_id, account_segment
    from {{ ref('dim_accounts') }}
),

-- Use last 3 months of data for stable churn rate estimate
recent_cohorts as (
    select
        avg(monthly_churn_rate_pct)                 as avg_monthly_churn_rate_pct,
        avg(nrr_pct)                                as avg_nrr_pct,
        avg(grr_pct)                                as avg_grr_pct
    from cohorts
    where month_date >= date_trunc('month', current_date - interval '3 months')
      and monthly_churn_rate_pct is not null
),

-- MRR per segment (active only)
segment_mrr as (
    select
        a.account_segment,
        count(distinct s.subscription_id)             as active_subscriptions,
        count(distinct s.workspace_id)                as active_accounts,
        sum(s.mrr_amount)                             as total_segment_mrr,
        avg(s.mrr_amount)                             as avg_mrr_per_subscription,
        sum(s.mrr_amount) / nullif(count(distinct s.workspace_id), 0)
                                                      as avg_mrr_per_account
    from subscriptions s
    left join accounts a on s.account_id = a.account_id
    where s.is_active
    group by 1
),

-- Overall active subscription snapshot
overall as (
    select
        count(distinct workspace_id)                as total_active_accounts,
        sum(mrr_amount)                             as total_active_mrr,
        avg(mrr_amount)                             as overall_avg_mrr
    from subscriptions
    where is_active
),

final as (
    select
        sm.account_segment,
        sm.active_subscriptions,
        sm.active_accounts,
        sm.total_segment_mrr,
        sm.avg_mrr_per_account,

        -- Retention benchmarks (portfolio-wide, last 3m)
        round(rc.avg_monthly_churn_rate_pct, 2)     as avg_monthly_churn_rate_pct,
        round(rc.avg_nrr_pct, 2)                    as avg_nrr_pct,
        round(rc.avg_grr_pct, 2)                    as avg_grr_pct,

        -- =================================================================
        -- LTV ESTIMATION
        -- LTV = Avg MRR / Monthly Churn Rate (in decimal form)
        -- =================================================================
        case
            when rc.avg_monthly_churn_rate_pct > 0
            then round(
                sm.avg_mrr_per_account
                    / (rc.avg_monthly_churn_rate_pct / 100.0),
                2
            )
            else null  -- Cannot estimate LTV without churn data
        end                                         as estimated_ltv,

        -- ARR per account
        round(sm.avg_mrr_per_account * 12, 2)       as avg_arr_per_account,

        -- LTV:ARR Ratio (rule of thumb: healthy SaaS > 3x)
        case
            when rc.avg_monthly_churn_rate_pct > 0
             and sm.avg_mrr_per_account > 0
            then round(
                (sm.avg_mrr_per_account / (rc.avg_monthly_churn_rate_pct / 100.0))
                    / (sm.avg_mrr_per_account * 12),
                2
            )
            else null
        end                                         as ltv_arr_ratio,

        -- Share of total MRR
        round(
            sm.total_segment_mrr / nullif(o.total_active_mrr, 0) * 100,
            2
        )                                           as pct_of_total_mrr,

        -- MetricFlow requires a time dimension for all measures
        cast(current_date as date)                  as snapshot_date

    from segment_mrr sm
    cross join recent_cohorts rc
    cross join overall o
)

select * from final
