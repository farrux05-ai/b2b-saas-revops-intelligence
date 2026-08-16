{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_attribution
-- MART: marketing
-- GRAIN: One row per account_id
--
-- TARGET AUDIENCE: Marketing Operations & Leadership — Campaign attribution & CAC analysis.
--
-- BUSINESS CONTRACT:
--   Maps revenue (MRR & Lifetime Revenue) and won deal counts to acquisition channels
--   using First-Touch UTM parameters stored on dim_accounts and int_crm_aggregated.
-- =============================================================================

with accounts as (
    select * from {{ ref('dim_accounts') }}
),

deals as (
    select 
        hubspot_company_id,
        won_deals_count
    from {{ ref('int_crm_aggregated') }}
),

final as (
    select
        a.account_id,
        a.workspace_name,
        
        -- Marketing Attribution Dimensions
        a.utm_source                                    as acquisition_channel,
        a.utm_campaign                                  as first_touch_campaign,
        
        -- Realized Revenue Metrics
        a.mrr,
        a.lifetime_revenue,
        
        -- Won Deal Volume
        coalesce(d.won_deals_count, 0)                  as won_deals_count,

        -- Required Date Dimension for MetricFlow / Semantic Layer
        cast(a.workspace_created_at as date)            as account_created_at
        
    from accounts a
    left join deals d
        on a.hubspot_company_id = d.hubspot_company_id
    where a.hubspot_company_id is not null
)

select * from final
