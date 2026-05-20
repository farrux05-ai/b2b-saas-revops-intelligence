-- =============================================================================
-- fct_subscriptions: Active Subscription Snapshot
-- Mart: finance
--
-- One row per active subscription. Finance's source of truth for MRR/ARR
-- reporting, plan mix analysis, and churn intent signals.
-- MRR computation lives here (not in staging — thin staging principle).
-- =============================================================================

with subscriptions as (
    select * from {{ ref('int_subscriptions_enriched') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

-- Seat utilization from int_finance_aggregated (actual seats used vs purchased)
finance as (
    select
        workspace_id,
        seats_used,
        seats_purchased
    from {{ ref('int_finance_aggregated') }}
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

        -- Revenue (computed centrally in int_subscriptions_enriched)
        s.unit_amount,
        s.seats_purchased                               as seats,
        s.mrr_amount,
        s.mrr_amount * 12                               as arr_amount,

        -- Seat Utilization
        coalesce(f.seats_used, 0)                       as seats_used,
        case
            when s.seats_purchased > 0
            then round(
                coalesce(f.seats_used, 0)::decimal / s.seats_purchased * 100,
                1
            )
            else null
        end                                             as seat_utilization_pct,

        -- Upsell/Downsell Signals
        (
            s.seats_purchased > 0
            and coalesce(f.seats_used, 0)::decimal / s.seats_purchased >= 0.9
        )                                               as is_upsell_candidate,
        (
            s.seats_purchased > 1
            and coalesce(f.seats_used, 0)::decimal / s.seats_purchased < 0.3
        )                                               as is_downsell_risk,

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
    left join finance f
        on s.workspace_id = f.workspace_id
)

select * from final
