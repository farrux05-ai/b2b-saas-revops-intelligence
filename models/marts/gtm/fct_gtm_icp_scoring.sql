{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_gtm_icp_scoring
-- DESCRIPTION: Modern GTM Scoring based on Clay/n8n enriched attributes.
-- This model demonstrates the power of GTM Engineering by assigning scores
-- to leads based on enriched firmographic and technographic data.
-- =============================================================================

with account_identity as (
    select * from {{ ref('int_accounts_joined') }}
),

scoring_logic as (
    select
        account_id,
        workspace_name,
        industry,
        annual_revenue,
        tech_stack,
        is_gtm_enriched,
        
        -- ICP SCORING ALGORITHM
        (
            -- 1. Technographic Score (From Clay)
            case 
                when tech_stack like '%AWS%' then 30 
                when tech_stack like '%GCP%' then 20
                else 10 
            end +
            
            -- 2. Firmographic Score (From Clay)
            case 
                when annual_revenue like '%500M%' then 50
                when annual_revenue like '%100M%' then 30
                else 10
            end +
            
            -- 3. Data Quality Bonus
            case when is_gtm_enriched then 20 else 0 end
        ) as total_icp_score

    from account_identity
)

select
    *,
    case 
        when total_icp_score >= 80 then 'Tier 1 (High Fit)'
        when total_icp_score >= 50 then 'Tier 2 (Medium Fit)'
        else 'Tier 3 (Low Fit)'
    end as icp_tier,
    
    -- Actionable Next Step for GTM Team
    case 
        when total_icp_score >= 80 then 'Route to Senior AE - Urgent'
        when total_icp_score >= 50 then 'Add to Automated Outbound Sequence'
        else 'Nurture via Marketing Email'
    end as gtm_action

from scoring_logic
order by total_icp_score desc
