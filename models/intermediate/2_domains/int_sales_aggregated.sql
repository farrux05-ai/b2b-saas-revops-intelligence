{{ config(materialized='view') }}

-- =============================================================================
-- int_sales_aggregated: CRM Sales Pipeline Metrics per Account
-- Layer: 2_domains
--
-- FIX: deal_sk no longer exists (removed in thin staging refactor).
-- Replaced count(deal_sk) with count(hubspot_deal_id).
-- =============================================================================

with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

final as (
    select
        hubspot_company_id,

        -- Open pipeline count: any deal not yet resolved
        count(hubspot_deal_id) filter (
            where deal_stage not in ('closedwon', 'closedlost')
        )                                               as open_deals_count,

        -- Historical revenue from won deals
        coalesce(
            sum(amount) filter (where deal_stage = 'closedwon'), 0
        )                                               as lifetime_revenue,

        -- Total won deals count (reusable in marketing marts)
        count(hubspot_deal_id) filter (
            where deal_stage = 'closedwon'
        )                                               as won_deals_count,

        -- Most recent win date: used to identify dormant customers
        max(closed_at) filter (where deal_stage = 'closedwon')
                                                        as last_won_date,

        -- Total deals ever created (pipeline velocity indicator)
        count(hubspot_deal_id)                          as total_deals_created

    from deals
    group by 1
)

select * from final
