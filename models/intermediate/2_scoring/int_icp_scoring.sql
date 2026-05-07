-- =============================================================================
-- MODEL: int_icp_scoring
-- DESCRIPTION: Calculates the ICP (Ideal Customer Profile) Fit Score for each account.
-- High Fit = 70+ | Medium Fit = 30-70 | Low Fit = <30
-- =============================================================================

with accounts as (
    -- Using the account dimension as the base
    select * from {{ ref('int_accounts_scored') }}
),

scoring as (
    select
        account_id,
        company_name,
        industry,
        account_segment,
        mrr,
        
        -- 1. Industry Fit (Technology & Finance are our sweet spots)
        case
            when industry in ('SaaS', 'Technology', 'Fintech', 'Software') then 40
            when industry in ('Ecommerce', 'Healthcare', 'Consulting') then 20
            else 5
        end                                             as industry_score,
        
        -- 2. Segment Fit (Enterprise/Mid-Market are priority)
        case
            when account_segment = 'Enterprise' then 40
            when account_segment = 'Mid-Market' then 20
            else 5
        end                                             as segment_score,
        
        -- 3. Revenue Fit (Already paying or has high potential)
        case
            when mrr > 1000 then 20
            when mrr > 500 then 10
            else 0
        end                                             as revenue_score

    from accounts
),

final as (
    select
        *,
        (industry_score + segment_score + revenue_score) as icp_score,
        
        case
            when (industry_score + segment_score + revenue_score) >= 70 then 'High Fit'
            when (industry_score + segment_score + revenue_score) >= 30 then 'Medium Fit'
            else 'Low Fit'
        end                                             as icp_tier
    from scoring
)

select * from final
