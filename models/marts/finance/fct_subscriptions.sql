{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_subscriptions: Active Subscription Snapshot
-- Mart: finance
--
-- One row per active subscription. Finance's source of truth for MRR/ARR
-- reporting, plan mix analysis, and cohort-level revenue tracking.
-- MRR computation lives here (not in staging — thin staging principle).
-- =============================================================================

with subscriptions as (
    select * from {{ ref('stg_stripe__subscriptions') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

final as (
    select
        -- Identity
        s.subscription_id,
        s.customer_id,
        s.workspace_id,
        sp.account_id,
        sp.workspace_name,
        sp.domain,

        -- Plan Info
        s.subscription_status,
        s.plan_id,

        -- Revenue (computed here per thin staging principle)
        s.unit_amount,
        s.quantity                                      as seats,
        case
            when s.unit_amount > 0
            then (s.unit_amount * s.quantity) / 100.0
            else 0
        end                                             as mrr_amount,
        case
            when s.unit_amount > 0
            then (s.unit_amount * s.quantity) / 100.0 * 12
            else 0
        end                                             as arr_amount,

        -- Status Flags
        s.subscription_status = 'active'               as is_active,
        s.subscription_status = 'trialing'             as is_trialing,
        s.subscription_status = 'past_due'             as is_past_due,
        s.subscription_status = 'canceled'             as is_canceled,
        s.is_cancel_at_period_end                       as is_churning_soon,

        -- Billing Period
        s.current_period_start_at,
        s.current_period_end_at,
        s.trial_end_at,
        s.created_at

    from subscriptions s
    left join spine sp
        on s.workspace_id = sp.internal_workspace_id
)

select * from final
