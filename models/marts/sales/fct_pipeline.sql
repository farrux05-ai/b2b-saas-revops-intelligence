{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_pipeline: Sales Deal Pipeline & Win/Loss Analysis
-- Mart: sales
--
-- Primary mart for the Sales team. One row per HubSpot deal.
-- Shows pipeline health, deal velocity, and conversion metrics.
-- Intended for: Pipeline reviews, forecasting, rep performance.
-- =============================================================================

with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

accounts as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        domain,
        account_segment,
        mrr,
        health_status
    from {{ ref('dim_accounts') }}
),

final as (
    select
        -- Deal Identity
        d.hubspot_deal_id,
        d.deal_name,
        d.hubspot_company_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,

        -- Pipeline Position
        d.pipeline,
        d.deal_stage,

        -- Financials
        coalesce(d.amount, 0)                           as deal_amount,
        coalesce(d.probability, 0)                      as win_probability,
        coalesce(d.amount, 0)
            * coalesce(d.probability, 0) / 100.0        as weighted_amount,

        -- Status Flags
        d.deal_stage in ('closedwon')                   as is_won,
        d.deal_stage in ('closedlost')                  as is_lost,
        d.deal_stage not in ('closedwon', 'closedlost') as is_open,

        -- Timing
        d.created_at,
        d.closed_at,

        -- Deal Velocity: days from creation to close
        case
            when d.closed_at is not null
             and d.closed_at > d.created_at
            then date_diff('day', d.created_at, d.closed_at)
        end                                             as days_to_close,

        -- Days open (for open deals)
        case
            when d.deal_stage not in ('closedwon', 'closedlost')
            then date_diff('day', d.created_at, current_timestamp)
        end                                             as days_open,

        -- Account Context (from dim_accounts)
        a.mrr                                           as account_current_mrr,
        a.health_status                                 as account_health_status

    from deals d
    left join accounts a
        on d.hubspot_company_id = a.hubspot_company_id
)

select * from final
