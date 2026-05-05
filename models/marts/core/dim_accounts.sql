{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- dim_accounts: The Golden Record for every Account
-- Mart: core
--
-- The single source of truth for account-level data across all GTM teams.
-- DO NOT add new business logic here. Pull from int_accounts_scored only.
-- FIX: now() replaced with current_timestamp (cross-adapter portable).
-- FIX: is_churning_soon added from finance domain.
-- =============================================================================

with master as (
    select * from {{ ref('int_accounts_scored') }}
),

final as (
    select
        -- Identity
        account_id,
        hubspot_company_id,
        internal_workspace_id,
        domain,
        workspace_name,
        company_name                                    as hubspot_company_name,
        industry,

        -- Revenue & Expansion
        mrr,
        active_mrr,
        mrr * 12                                        as arr,
        account_segment,
        latest_subscription_status                      as subscription_status,
        current_plan,
        seat_limit,
        seats_used,
        seat_utilization_pct,
        is_ready_for_upsell,
        is_churning_soon,

        -- Health, Risk & Churn
        health_status,
        health_reason,
        mrr_at_risk,
        is_payment_failing,

        -- PLG & Product
        is_pql,
        total_product_events                            as product_events_count,
        last_activity_at,

        -- CRM & Sales
        total_tickets,
        open_tickets,
        open_deals_count,
        lifetime_revenue,
        last_won_date,

        -- Audit
        current_timestamp                               as last_updated_at

    from master
)

select * from final
