-- =============================================================================
-- fct_pipeline: Sales Deal Pipeline & Win/Loss Analysis
-- Mart: sales
--
-- Primary mart for the Sales team. One row per HubSpot deal.
-- Shows pipeline health, deal velocity, and conversion metrics.
-- Intended for: Pipeline reviews, forecasting, rep performance.
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
        -- Deal Identity
        d.hubspot_deal_id,
        d.deal_name,
        d.hubspot_company_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,

        -- Pipeline Position
        d.pipeline,
        d.deal_stage,

        -- Financials
        d.amount                                        as deal_amount,
        d.probability                                   as win_probability,
        d.weighted_amount,

        -- Status Flags
        d.is_won,
        d.is_lost,
        d.is_open,

        -- Timing
        d.created_at,
        d.closed_at,

        -- Deal Velocity
        d.days_to_close,
        d.days_open,
        d.is_stale,
        d.deal_age_bucket,

        -- Benchmark: Average days to close for WON deals
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
