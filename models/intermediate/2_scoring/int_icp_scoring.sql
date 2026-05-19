{{ config(materialized='view') }}
-- Grain: one row per account

-- =============================================================================
-- MODEL: int_icp_scoring
-- DESCRIPTION: Calculates the ICP (Ideal Customer Profile) Fit Score for each account.
-- Layer: 2_scoring
-- =============================================================================

with spine as (
    select * from {{ ref('int_accounts_joined') }}
),

hubspot as (
    select * from {{ ref('stg_hubspot__companies') }}
),

finance as (
    select * from {{ ref('int_finance_aggregated') }}
),

scoring_base as (
    select
        s.account_id,
        h.company_name,
        h.industry,
        f.total_mrr                                     as mrr,
        
        -- Move segmentation logic here to keep it in Layer 2
        case
            when coalesce(f.total_mrr, 0) * 12 >= 50000 then 'Enterprise'
            when coalesce(f.total_mrr, 0) * 12 >= 10000 then 'Mid-Market'
            when coalesce(f.total_mrr, 0) * 12 > 0 then 'SMB'
            else 'Trial/Free'
        end                                             as account_segment

    from spine s
    left join hubspot h on s.hubspot_company_id = h.hubspot_company_id
    left join finance f on s.internal_workspace_id = f.workspace_id
),

industry_scores as (
    select * from {{ ref('icp_industry_scores') }}
),

segment_scores as (
    select * from {{ ref('icp_segment_scores') }}
),

scoring as (
    select
        sb.*,
        -- 1. Industry Fit (Technology & Finance are our sweet spots)
        coalesce(ind.industry_score, 5)                 as industry_score,
        
        -- 2. Segment Fit (Enterprise/Mid-Market are priority)
        coalesce(seg.segment_score, 5)                  as segment_score,
        
        -- 3. Revenue Fit (Already paying or has high potential)
        case
            when sb.mrr > 1000 then 20
            when sb.mrr > 500 then 10
            else 0
        end                                             as revenue_score

    from scoring_base sb
    left join industry_scores ind on sb.industry = ind.industry
    left join segment_scores seg on sb.account_segment = seg.account_segment
),

final as (
    select
        account_id,
        company_name,
        industry,
        account_segment,
        mrr,
        (industry_score + segment_score + revenue_score) as icp_score,
        
        case
            when (industry_score + segment_score + revenue_score) >= 70 then 'High Fit'
            when (industry_score + segment_score + revenue_score) >= 30 then 'Medium Fit'
            else 'Low Fit'
        end                                             as icp_tier
    from scoring
)

select * from final
