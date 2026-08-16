{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_deals_enriched
-- LAYER: 2_domains (Domain Models)
-- GRAIN: One row per hubspot_deal_id
--
-- ARCHITECTURAL RATIONALE:
--   Created to solve dbt Anti-pattern #13 (marts querying staging directly).
--   Previously, fct_pipeline queried stg_hubspot__deals directly.
--   Now, fct_pipeline consumes this enriched intermediate deal-level model.
--
-- DIFFERENCE FROM int_crm_aggregated:
--   - int_crm_aggregated: Aggregated at the hubspot_company_id grain (1 row per company).
--   - int_deals_enriched: Un-aggregated at the hubspot_deal_id grain (1 row per deal).
--
-- BUSINESS RESPONSIBILITY:
--   Enriches raw deals with probability-weighted revenue (weighted_amount),
--   lifecycle status flags (is_won, is_lost, is_open), cycle metrics (days_to_close, days_open),
--   stale deal flags (>90d open), deal age buckets, and joins account context (account_id).
-- =============================================================================

with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

-- Account backbone for account context resolution
accounts as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        domain
    from {{ ref('int_accounts_joined') }}
),

final as (
    select
        -- Deal Identity
        d.hubspot_deal_id,
        d.hubspot_company_id,
        d.deal_name,
        d.pipeline,
        d.deal_stage,

        -- Financials & Weighting
        coalesce(d.amount, 0)                           as amount,
        coalesce(d.probability, 0)                      as probability,
        -- Probability-weighted deal value
        coalesce(d.amount, 0)
            * coalesce(d.probability, 0) / 100.0        as weighted_amount,

        -- Status Flags
        d.deal_stage = 'closedwon'                      as is_won,
        d.deal_stage = 'closedlost'                     as is_lost,
        d.deal_stage not in ('closedwon', 'closedlost') as is_open,

        -- Time & Duration Metrics
        d.created_at,
        d.closed_at,

        -- Sales cycle duration in days (for closed-won/closed-lost deals)
        case
            when d.closed_at is not null
             and d.closed_at > d.created_at
            then datediff('day', d.created_at, d.closed_at)
        end                                             as days_to_close,

        -- Age in days for currently open deals
        case
            when d.deal_stage not in ('closedwon', 'closedlost')
            then datediff('day', d.created_at, current_timestamp)
        end                                             as days_open,

        -- Stale Deal Indicator (Open > 90 days without closure)
        (d.deal_stage not in ('closedwon', 'closedlost')
         and datediff('day', d.created_at, current_timestamp) > 90
        )                                               as is_stale,

        -- Deal Age Categorization Bucket
        case
            when d.deal_stage in ('closedwon', 'closedlost') then 'Closed'
            when datediff('day', d.created_at, current_timestamp) <= 30  then '0-30 days'
            when datediff('day', d.created_at, current_timestamp) <= 60  then '31-60 days'
            when datediff('day', d.created_at, current_timestamp) <= 90  then '61-90 days'
            else '90+ days (Stale)'
        end                                             as deal_age_bucket,

        -- Resolved Account Context (from int_accounts_joined)
        a.account_id,
        a.workspace_name,
        a.domain

    from deals d
    left join accounts a on d.hubspot_company_id = a.hubspot_company_id
)

select * from final
