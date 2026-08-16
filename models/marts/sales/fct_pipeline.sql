{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_pipeline
-- MART: sales
-- GRAIN: One row per hubspot_deal_id
--
-- TARGET AUDIENCE: Sales Leaders & Reps — Pipeline health, deal velocity, forecasting.
--
-- BUSINESS CONTRACT:
--   Consumes deal-level enriched model int_deals_enriched (resolves dbt Anti-pattern #13).
--   Joins with dim_accounts for account context (MRR, Health Status, Segment).
-- =============================================================================

with deals as (
    select * from {{ ref('int_deals_enriched') }}
),

accounts as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        domain,
        account_segment,
        mrr,
        health_status
    from {{ ref('dim_accounts') }}
),

final as (
    select
        -- Deal Identity & Foreign Keys
        d.hubspot_deal_id,
        d.deal_name,
        d.hubspot_company_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,

        -- Sales Pipeline Stage
        d.pipeline,
        d.deal_stage,

        -- Financial Amounts & Weighted Probability
        d.amount                                        as deal_amount,
        d.probability                                   as win_probability,
        d.weighted_amount,

        -- Deal Status Flags
        d.is_won,
        d.is_lost,
        d.is_open,

        -- Timestamps & Velocity
        d.created_at,
        d.closed_at,
        d.days_to_close,
        d.days_open,
        d.is_stale,
        d.deal_age_bucket,

        -- Benchmark: Window average days to close for Won deals
        avg(
            case
                when d.is_won
                 and d.closed_at is not null
                then d.days_to_close
            end
        ) over ()                                       as avg_won_days_to_close,

        -- Account Context (from dim_accounts)
        a.mrr                                           as account_current_mrr,
        a.health_status                                 as account_health_status

    from deals d
    left join accounts a
        on d.hubspot_company_id = a.hubspot_company_id
)

select * from final
