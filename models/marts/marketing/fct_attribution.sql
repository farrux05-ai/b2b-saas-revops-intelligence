{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_attribution: Marketing Attribution 
-- Mart: marketing
--
-- Maps revenue (deals/MRR) to marketing channels using UTM parameters from
-- HubSpot companies (First-Touch attribution).
-- =============================================================================

with accounts as (
    select * from {{ ref('dim_accounts') }}
),

deals as (
    select * from {{ ref('stg_hubspot__deals') }}
    where deal_stage = 'closed_won'
),

final as (
    select
        a.account_id,
        a.workspace_name,
        
        -- Real Attribution Fields
        a.utm_source                                    as acquisition_channel,
        a.utm_campaign                                  as first_touch_campaign,
        
        -- Revenue Metrics
        a.mrr,
        a.lifetime_revenue,
        
        -- Deal counts from this channel
        count(d.hubspot_deal_id) as won_deals_count
        
    from accounts a
    left join deals d
        on a.hubspot_company_id = d.hubspot_company_id
    where a.hubspot_company_id is not null
    group by 1, 2, 3, 4, 5, 6
)

select * from final
