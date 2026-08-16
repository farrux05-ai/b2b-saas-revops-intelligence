{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_icp_scoring
-- LAYER: 2_scoring (Scoring & Classification Layer)
-- GRAIN: One row per account_id
--
-- BUSINESS RESPONSIBILITY:
--   Calculates the ICP (Ideal Customer Profile) Fit Score at the account level.
--   Combines industry fit (icp_industry_scores seed), segment fit (icp_segment_scores seed),
--   and MRR revenue fit from int_billing_aggregated.
--   Classifies accounts into ICP tiers (High Fit / Medium Fit / Low Fit) used downstream
--   in fct_pql_signals to construct the GTM Priority Matrix for Sales.
-- =============================================================================

with spine as (
    select
        account_id,
        hubspot_company_id,
        internal_workspace_id
    from {{ ref('int_accounts_joined') }}
),

hubspot as (
    select
        hubspot_company_id,
        company_name,
        industry,
        employee_count
    from {{ ref('stg_hubspot__companies') }}
),

-- Billing domain: extract total MRR per workspace
billing as (
    select
        workspace_id,
        total_mrr
    from {{ ref('int_billing_aggregated') }}
),

industry_scores as (
    select * from {{ ref('icp_industry_scores') }}
),

segment_scores as (
    select * from {{ ref('icp_segment_scores') }}
),

-- Construct base attributes and compute revenue-based account segment (ARR thresholding)
scoring_base as (
    select
        s.account_id,
        h.company_name,
        h.industry,
        h.employee_count,
        coalesce(b.total_mrr, 0)                        as mrr,

        -- Revenue Segmentation: Enterprise (ARR >= $50k) / Mid-Market / SMB / Trial/Free
        case
            when coalesce(b.total_mrr, 0) * 12 >= 50000 then 'Enterprise'
            when coalesce(b.total_mrr, 0) * 12 >= 10000 then 'Mid-Market'
            when coalesce(b.total_mrr, 0) * 12 > 0      then 'SMB'
            else 'Trial/Free'
        end                                             as account_segment

    from spine s
    left join hubspot h  on s.hubspot_company_id = h.hubspot_company_id
    left join billing b  on s.internal_workspace_id = b.workspace_id
),

-- Compute component fit scores
scoring as (
    select
        sb.*,

        -- 1. Industry Fit Score (Looked up from seeds/icp_industry_scores.csv)
        coalesce(ind.industry_score, 5)                 as industry_score,

        -- 2. Segment Fit Score (Looked up from seeds/icp_segment_scores.csv)
        coalesce(seg.segment_score, 5)                  as segment_score,

        -- 3. Revenue Fit Score (Paying vs Non-paying potential)
        case
            when sb.mrr > 1000 then 20
            when sb.mrr > 500  then 10
            else 0
        end                                             as revenue_score

    from scoring_base sb
    left join industry_scores ind on sb.industry = ind.industry
    left join segment_scores seg  on sb.account_segment = seg.account_segment
)

select
    account_id,
    company_name,
    industry,
    employee_count,
    account_segment,
    mrr,

    -- Total composite ICP score
    (industry_score + segment_score + revenue_score)    as icp_score,

    -- ICP Tier Classification
    case
        when (industry_score + segment_score + revenue_score) >= 70 then 'High Fit'
        when (industry_score + segment_score + revenue_score) >= 30 then 'Medium Fit'
        else 'Low Fit'
    end                                                 as icp_tier

from scoring
