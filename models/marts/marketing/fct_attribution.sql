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
    select 
        hubspot_company_id,
        won_deals_count
    from {{ ref('int_sales_aggregated') }}
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
        coalesce(d.won_deals_count, 0)                  as won_deals_count,

        -- MetricFlow requires a time dimension
        cast(a.workspace_created_at as date)            as account_created_at
        
    from accounts a
    left join deals d
        on a.hubspot_company_id = d.hubspot_company_id
    where a.hubspot_company_id is not null
)

select * from final
