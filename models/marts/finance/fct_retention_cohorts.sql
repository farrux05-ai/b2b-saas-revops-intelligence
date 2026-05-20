{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_retention_cohorts
-- LAYER: Marts / Finance
--
-- PURPOSE: Monthly NRR and GRR cohort analysis.
-- This is the #1 investor metric for B2B SaaS.
--
-- DEFINITIONS:
--   GRR (Gross Revenue Retention) = 1 - Churn Rate
--       Measures revenue retained before any upsell/expansion.
--       Formula: (Starting MRR - Churned MRR - Contracted MRR) / Starting MRR
--       Healthy SaaS: > 85%
--
--   NRR (Net Revenue Retention) = Revenue retained + Expansion / Starting MRR
--       Measures total revenue impact including expansions.
--       Formula: (Starting MRR - Churned MRR + Expanded MRR) / Starting MRR
--       Best-in-class SaaS: > 120% (means customers spend more over time)
-- =============================================================================

with waterfall as (
    select * from {{ ref('fct_mrr_waterfall') }}
),

-- Aggregate movements per cohort-month
monthly_movements as (
    select
        month_date,

        -- Starting MRR for the period (previous month retained value)
        sum(case when mrr_movement_type in ('retained', 'expansion', 'contraction')
            then previous_month_mrr else 0 end)    as starting_mrr,

        -- New business (excluded from retention calc)
        sum(case when mrr_movement_type = 'new'
            then mrr else 0 end)                    as new_mrr,

        -- Expansions: accounts paying MORE than last month
        sum(case when mrr_movement_type = 'expansion'
            then mrr_change_amount else 0 end)      as expansion_mrr,

        -- Contractions: accounts paying LESS (but not churned)
        sum(case when mrr_movement_type = 'contraction'
            then abs(mrr_change_amount) else 0 end) as contraction_mrr,

        -- Churn: accounts that went to zero
        sum(case when mrr_movement_type = 'churn'
            then previous_month_mrr else 0 end)     as churned_mrr,

        -- Resurrections (churned accounts coming back)
        sum(case when mrr_movement_type = 'resurrection'
            then mrr else 0 end)                    as resurrection_mrr,

        -- Total ending MRR for the period
        sum(mrr)                                    as ending_mrr,

        -- Count of paying accounts at start and end
        count(distinct case when mrr_movement_type != 'new' and previous_month_mrr > 0
            then account_id end)                    as starting_accounts,
        count(distinct case when mrr > 0
            then account_id end)                    as ending_accounts,
        count(distinct case when mrr_movement_type = 'churn'
            then account_id end)                    as churned_accounts

    from waterfall
    group by 1
),

final as (
    select
        month_date,

        -- MRR Movements (all in USD)
        starting_mrr,
        new_mrr,
        expansion_mrr,
        contraction_mrr,
        churned_mrr,
        resurrection_mrr,
        ending_mrr,

        -- Net MRR Movement breakdown
        new_mrr + expansion_mrr + resurrection_mrr
            - contraction_mrr - churned_mrr         as net_mrr_change,

        -- Account counts
        starting_accounts,
        ending_accounts,
        churned_accounts,

        -- =================================================================
        -- RETENTION METRICS
        -- =================================================================

        -- GRR: Revenue retained without expansions (ceiling = 100%)
        -- Null guard: avoid division by zero when starting_mrr = 0
        case
            when starting_mrr > 0
            then round(
                least(
                    (starting_mrr - churned_mrr - contraction_mrr) / starting_mrr,
                    1.0  -- GRR cannot exceed 100%
                ) * 100,
                2
            )
            else null
        end                                         as grr_pct,

        -- NRR: Revenue retained including expansion (can exceed 100%)
        case
            when starting_mrr > 0
            then round(
                (starting_mrr - churned_mrr - contraction_mrr + expansion_mrr)
                    / starting_mrr * 100,
                2
            )
            else null
        end                                         as nrr_pct,

        -- Monthly Churn Rate
        case
            when starting_mrr > 0
            then round(churned_mrr / starting_mrr * 100, 2)
            else null
        end                                         as monthly_churn_rate_pct,

        -- Logo Churn Rate (by account count, not revenue)
        case
            when starting_accounts > 0
            then round(churned_accounts::decimal / starting_accounts * 100, 2)
            else null
        end                                         as logo_churn_rate_pct

    from monthly_movements
)

select * from final
