{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_accounts_health: Account Health & Churn Risk Dashboard
-- Mart: customer_success
--
-- Primary mart for the CS (Customer Success) team.
-- Shows every paying account's health, churn risk signals, and support burden.
-- Intended for: Churn prevention workflows, QBRs, CS prioritization.
-- =============================================================================

with accounts as (
    select * from {{ ref('int_accounts_scored') }}
),

final as (
    select
        -- Identity
        account_id,
        domain,
        workspace_name,
        account_segment,
        current_plan,

        -- Revenue Exposure
        mrr,
        arr,
        mrr_at_risk,

        -- Health Signals
        health_status,
        health_reason,
        latest_subscription_status                      as subscription_status,

        -- Churn Risk Signals (3 distinct warning types)
        is_payment_failing,                             -- Silent churn: card declined
        is_churning_soon,                               -- Intent churn: cancel scheduled
        case
            when last_activity_at < current_timestamp - interval '30 days'
            then true else false
        end                                             as is_low_engagement,

        -- Support Burden
        total_tickets,
        open_tickets,
        high_priority_tickets,
        avg_resolution_hours,
        last_ticket_at,

        -- Product Engagement
        total_product_events                            as product_events_count,
        last_activity_at,
        is_pql,

        -- Expansion Signals
        seat_utilization_pct,
        seats_used,
        seat_limit,
        is_ready_for_upsell

    from accounts
    -- CS team only cares about accounts that have entered billing
    where latest_subscription_status is not null
)

select * from final
