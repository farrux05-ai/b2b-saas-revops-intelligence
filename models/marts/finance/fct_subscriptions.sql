-- =============================================================================
-- fct_subscriptions: Active Subscription Snapshot
-- Mart: finance
--
-- One row per active subscription. Finance's source of truth for MRR/ARR
-- reporting, plan mix analysis, and churn intent signals.
-- MRR computation lives here (not in staging — thin staging principle).
-- =============================================================================

with billing as (
    select * from {{ ref('int_billing_aggregated') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

final as (
    select
        -- Identity
        b.customer_id,
        b.workspace_id,
        sp.account_id,
        sp.workspace_name,
        sp.domain,

        -- Plan Info
        b.latest_subscription_status                    as subscription_status,
        b.current_plan                                  as plan_id,

        -- Revenue
        b.active_mrr                                    as mrr_amount,
        b.active_mrr * 12                               as arr_amount,

        -- Seat Utilization
        b.seats_purchased,
        b.seats_used,
        b.seat_utilization_pct * 100                    as seat_utilization_pct,

        -- Upsell/Downsell Signals
        b.is_upsell_candidate,
        b.is_downsell_risk,

        -- Status Flags
        b.latest_subscription_status = 'active'         as is_active,
        b.latest_subscription_status = 'trialing'       as is_trialing,
        b.latest_subscription_status = 'past_due'       as is_past_due,
        b.latest_subscription_status = 'canceled'       as is_canceled,
        b.is_churning_soon,

        -- Billing Period
        b.current_period_start_at,
        b.current_period_end_at,
        b.trial_end_at

    from billing b
    left join spine sp
        on b.workspace_id = sp.internal_workspace_id
)

select * from final
