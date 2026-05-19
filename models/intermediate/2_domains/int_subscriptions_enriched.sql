{{ config(materialized='view') }}

-- =============================================================================
-- int_subscriptions_enriched: Enriched Subscriptions with MRR
-- Layer: 2_domains
--
-- DRY Principle: MRR logic is centralized here instead of duplicated across marts.
-- =============================================================================

with subscriptions as (
    select * from {{ ref('stg_stripe__subscriptions') }}
),

enriched as (
    select
        *,
        -- Compute MRR using the centralized macro
        {{ calculate_mrr('unit_amount', 'seats_purchased') }} as mrr_amount,
        
        -- Identify the latest subscription for status/plan extraction
        row_number() over (
            partition by workspace_id 
            order by created_at desc
        ) as recency_rank
    from subscriptions
)

select * from enriched
