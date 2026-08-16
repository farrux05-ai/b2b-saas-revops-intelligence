{{ config(materialized='table') }}

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
        count(
            case when deal_stage not in ('closedwon', 'closedlost') then hubspot_deal_id end
        )                                               as open_deals_count,

        -- Historical revenue from won deals
        coalesce(
            sum(case when deal_stage = 'closedwon' then amount else 0 end), 0
        )                                               as lifetime_revenue,

        -- Total won deals count (reusable in marketing marts)
        count(
            case when deal_stage = 'closedwon' then hubspot_deal_id end
        )                                               as won_deals_count,

        -- Most recent win date: used to identify dormant customers
        max(
            case when deal_stage = 'closedwon' then closed_at end
        )                                               as last_won_date,

        -- Total deals ever created (pipeline velocity indicator)
        count(hubspot_deal_id)                          as total_deals_created

    from deals
    group by 1
)

select * from final
