{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_retention_cohorts
-- MART: finance
-- GRAIN: one row per month_date (portfolio aggregate)
-- MATERIALIZED: table — fct_unit_economics ko'p so'raydi
--
-- AUDITORIYA: Finance + Investor — NRR/GRR cohort tahlil.
-- O'ZGARISH yo'q — fct_mrr_waterfall dan oladi.
-- =============================================================================

with waterfall as (
    select * from {{ ref('fct_mrr_waterfall') }}
),

monthly_movements as (
    select
        month_date,

        sum(case when mrr_movement_type in ('retained', 'expansion', 'contraction')
            then previous_month_mrr else 0 end)         as starting_mrr,
        sum(case when mrr_movement_type = 'new'
            then mrr else 0 end)                        as new_mrr,
        sum(case when mrr_movement_type = 'expansion'
            then mrr_change_amount else 0 end)          as expansion_mrr,
        sum(case when mrr_movement_type = 'contraction'
            then abs(mrr_change_amount) else 0 end)     as contraction_mrr,
        sum(case when mrr_movement_type = 'churn'
            then previous_month_mrr else 0 end)         as churned_mrr,
        sum(case when mrr_movement_type = 'resurrection'
            then mrr else 0 end)                        as resurrection_mrr,
        sum(mrr)                                        as ending_mrr,

        count(distinct case
            when mrr_movement_type != 'new'
             and previous_month_mrr > 0
            then account_id end)                        as starting_accounts,
        count(distinct case
            when mrr > 0 then account_id end)           as ending_accounts,
        count(distinct case
            when mrr_movement_type = 'churn'
            then account_id end)                        as churned_accounts

    from waterfall
    group by 1
)

select
    month_date,

    -- MRR harakatlari
    starting_mrr,
    new_mrr,
    expansion_mrr,
    contraction_mrr,
    churned_mrr,
    resurrection_mrr,
    ending_mrr,
    new_mrr + expansion_mrr + resurrection_mrr
        - contraction_mrr - churned_mrr                 as net_mrr_change,

    -- Account soni
    starting_accounts,
    ending_accounts,
    churned_accounts,

    -- ── GRR: expansion qo'shilmaydi, ceiling = 100% ──────────────────────
    case
        when starting_mrr > 0
        then round(
            least(
                (starting_mrr - churned_mrr - contraction_mrr)
                / nullif(starting_mrr, 0),
                1.0
            ) * 100, 2)
    end                                                 as grr_pct,

    -- ── NRR: expansion kiritiladi, 100%+ bo'lishi mumkin ─────────────────
    case
        when starting_mrr > 0
        then round(
            (starting_mrr - churned_mrr - contraction_mrr + expansion_mrr)
            / nullif(starting_mrr, 0) * 100, 2)
    end                                                 as nrr_pct,

    -- ── Oylik churn rate ──────────────────────────────────────────────────
    case
        when starting_mrr > 0
        then round(churned_mrr / nullif(starting_mrr, 0) * 100, 2)
    end                                                 as monthly_churn_rate_pct,

    -- ── Logo churn rate (account soni bo'yicha) ──────────────────────────
    case
        when starting_accounts > 0
        then round(
            churned_accounts::decimal
            / nullif(starting_accounts, 0) * 100, 2)
    end                                                 as logo_churn_rate_pct

from monthly_movements
