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
-- Maps revenue (deals/MRR) to marketing channels. Since the raw mock data lacks
-- explicit utm_source/campaign tracking, this model assigns synthetic channels
-- based on industry to simulate a First-Touch attribution model.
-- =============================================================================

with accounts as (
    select * from {{ ref('dim_accounts') }}
),

deals as (
    select * from {{ ref('stg_hubspot__deals') }}
    where deal_stage = 'closed_won'
),

synthetic_attribution as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        industry,
        mrr,
        lifetime_revenue,
        
        -- Synthetic Channel Assignment
        case
            when industry in ('Technology', 'Software') then 'Organic Search'
            when industry in ('Healthcare', 'Finance') then 'Outbound Sales'
            when industry in ('Retail', 'E-commerce') then 'Paid Social'
            else 'Direct Traffic'
        end as acquisition_channel,
        
        -- Synthetic Campaign Assignment
        case
            when industry in ('Technology', 'Software') then 'Q1_SEO_Push'
            when industry in ('Healthcare', 'Finance') then 'Cold_Email_Sequence_A'
            when industry in ('Retail', 'E-commerce') then 'LinkedIn_Ads_B2B'
            else 'None'
        end as first_touch_campaign

    from accounts
    where hubspot_company_id is not null
),

final as (
    select
        a.account_id,
        a.workspace_name,
        a.acquisition_channel,
        a.first_touch_campaign,
        
        -- Revenue Metrics
        a.mrr,
        a.lifetime_revenue,
        
        -- Deal counts from this channel
        count(d.hubspot_deal_id) as won_deals_count
        
    from synthetic_attribution a
    left join deals d
        on a.hubspot_company_id = d.hubspot_company_id
    group by 1, 2, 3, 4, 5, 6
)

select * from final
