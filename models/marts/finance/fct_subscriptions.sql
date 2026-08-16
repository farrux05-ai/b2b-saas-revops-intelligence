{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_subscriptions
-- MART: finance
-- GRAIN: One row per workspace subscription record
--
-- TARGET AUDIENCE: Finance & Executive Leadership — MRR/ARR reporting, plan mix, churn intent.
--
-- BUSINESS CONTRACT:
--   Sourced directly from int_billing_aggregated.
--   Computes active/trialing subscription statuses, seat utilization, and upsell candidate flags.
-- =============================================================================

with billing as (
    select * from {{ ref('int_billing_aggregated') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

final as (
    select
        -- Identity & Foreign Keys
        b.customer_id,
        b.workspace_id,
        sp.account_id,
        sp.workspace_name,
        sp.domain,

        -- Plan & Status Dimensions
        b.latest_subscription_status                    as subscription_status,
        b.current_plan                                  as plan_id,

        -- Revenue Computations
        b.active_mrr                                    as mrr_amount,
        b.active_mrr * 12                               as arr_amount,

        -- Seat Utilization & Capacity
        b.seats_purchased,
        b.seats_used,
        b.seat_utilization_pct * 100                    as seat_utilization_pct,

        -- Upsell / Downsell Risk Flags
        b.is_upsell_candidate,
        b.is_downsell_risk,

        -- Status Flags
        b.latest_subscription_status = 'active'         as is_active,
        b.latest_subscription_status = 'trialing'       as is_trialing,
        b.latest_subscription_status = 'past_due'       as is_past_due,
        b.latest_subscription_status = 'canceled'       as is_canceled,
        b.is_churning_soon,

        -- Subscription Billing Timestamps
        b.current_period_start_at,
        b.current_period_end_at,
        b.trial_end_at

    from billing b
    left join spine sp
        on b.workspace_id = sp.internal_workspace_id
)

select * from final
