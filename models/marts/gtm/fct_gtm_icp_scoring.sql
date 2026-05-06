{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_gtm_icp_scoring
-- DESCRIPTION: Hybrid GTM Scoring Engine.
-- This model combines External Data (Clay/HubSpot) with Internal Data (Usage/Support).
-- 
-- Hybrid Philosophy:
-- 1. Clay (Outside): Tells us WHO they are (Potential).
-- 2. Product/Support (Inside): Tells us WHAT they are doing (Intent/Friction).
-- =============================================================================

with account_identity as (
    select * from {{ ref('int_accounts_joined') }}
),

usage_stats as (
    select * from {{ ref('int_usage_aggregated') }}
),

support_stats as (
    select * from {{ ref('int_support_aggregated') }}
),

hybrid_scoring as (
    select
        acc.account_id,
        acc.workspace_name,
        acc.industry,
        acc.annual_revenue,
        acc.tech_stack,
        
        -- 1. CLAY SCORE (External Firmographics - Handled by Clay outside WH)
        -- We map their results here to provide context.
        (case 
            when acc.annual_revenue like '%500M%' then 30
            when acc.annual_revenue like '%100M%' then 20
            else 10
        end) as clay_firmographic_score,

        -- 2. PRODUCT INTENT SCORE (Internal Usage - Only Warehouse knows this)
        (case 
            when coalesce(usg.is_pql, false) then 40
            when coalesce(usg.total_product_events, 0) > 100 then 20
            else 0
        end) as product_intent_score,

        -- 3. SUPPORT FRICTION (Internal Health - Only Warehouse knows this)
        (case 
            when coalesce(sup.open_tickets, 0) > 3 then -15
            else 0
        end) as support_friction_score,

        -- TOTAL HYBRID SCORE
        (
            (case when acc.annual_revenue like '%500M%' then 30 when acc.annual_revenue like '%100M%' then 20 else 10 end) + 
            (case when coalesce(usg.is_pql, false) then 40 when coalesce(usg.total_product_events, 0) > 100 then 20 else 0 end) + 
            (case when coalesce(sup.open_tickets, 0) > 3 then -15 else 0 end)
        ) as total_hybrid_score

    from account_identity acc
    left join usage_stats usg on acc.internal_workspace_id = usg.workspace_id
    left join support_stats sup on acc.account_id = sup.account_id
)

select
    *,
    -- HYBRID ACTIONABLE SEGMENTATION
    case 
        when total_hybrid_score >= 70 and product_intent_score >= 40 then 'Expansion Target (Up-sell Now!)'
        when total_hybrid_score >= 50 and product_intent_score < 20 then 'Activation Risk (CS Intervention)'
        when support_friction_score < 0 then 'High Friction (Fix Support First)'
        else 'Standard Nurture'
    end as hybrid_gtm_action

from hybrid_scoring
order by total_hybrid_score desc
