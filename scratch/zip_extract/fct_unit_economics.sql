{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_unit_economics
-- MART: finance
-- GRAIN: one row per account_segment
--
-- AUDITORIYA: Finance + Investor — LTV, LTV:ARR ratio segment bo'yicha.
-- O'ZGARISH yo'q — fct_retention_cohorts + fct_subscriptions + dim_accounts dan.
-- =============================================================================

with cohorts as (
    select * from {{ ref('fct_retention_cohorts') }}
),

subscriptions as (
    select * from {{ ref('fct_subscriptions') }}
),

accounts as (
    select account_id, account_segment
    from {{ ref('dim_accounts') }}
),

-- Oxirgi 3 oylik o'rtacha churn rate (barqaror hisob uchun)
recent_cohorts as (
    select
        avg(monthly_churn_rate_pct)                     as avg_monthly_churn_rate_pct,
        avg(nrr_pct)                                    as avg_nrr_pct,
        avg(grr_pct)                                    as avg_grr_pct
    from cohorts
    where month_date >= cast(
        date_trunc('month', current_date - interval '3 months') as date)
      and monthly_churn_rate_pct is not null
),

-- Segment bo'yicha MRR (faqat aktiv subscriptionlar)
segment_mrr as (
    select
        a.account_segment,
        count(distinct s.workspace_id)                  as active_accounts,
        sum(s.mrr_amount)                               as total_segment_mrr,
        sum(s.mrr_amount)
            / nullif(count(distinct s.workspace_id), 0) as avg_mrr_per_account
    from subscriptions s
    left join accounts a on s.account_id = a.account_id
    where s.is_active
    group by 1
),

overall as (
    select sum(mrr_amount) as total_active_mrr
    from subscriptions
    where is_active
)

select
    sm.account_segment,
    sm.active_accounts,
    sm.total_segment_mrr,
    sm.avg_mrr_per_account,

    -- Retention benchmarklar (portfolio, oxirgi 3 oy)
    round(rc.avg_monthly_churn_rate_pct, 2)             as avg_monthly_churn_rate_pct,
    round(rc.avg_nrr_pct, 2)                            as avg_nrr_pct,
    round(rc.avg_grr_pct, 2)                            as avg_grr_pct,

    -- LTV = Avg MRR / Monthly Churn Rate
    case
        when rc.avg_monthly_churn_rate_pct > 0
        then round(
            sm.avg_mrr_per_account
            / (rc.avg_monthly_churn_rate_pct / 100.0), 2)
    end                                                 as estimated_ltv,

    -- ARR per account
    round(sm.avg_mrr_per_account * 12, 2)               as avg_arr_per_account,

    -- LTV:ARR ratio (sog'lom SaaS > 3x)
    case
        when rc.avg_monthly_churn_rate_pct > 0
         and sm.avg_mrr_per_account > 0
        then round(
            (sm.avg_mrr_per_account / (rc.avg_monthly_churn_rate_pct / 100.0))
            / (sm.avg_mrr_per_account * 12), 2)
    end                                                 as ltv_arr_ratio,

    -- Jami MRR dagi ulushi
    round(sm.total_segment_mrr
        / nullif(o.total_active_mrr, 0) * 100, 2)      as pct_of_total_mrr,

    -- MetricFlow vaqt dimensiyasi uchun
    cast(current_date as date)                          as snapshot_date

from segment_mrr sm
cross join recent_cohorts rc
cross join overall o
