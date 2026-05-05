{{ config(materialized='view') }}

-- =============================================================================
-- int_finance_aggregated: Billing & Revenue Metrics per Account
-- Layer: 2_domains
--
-- FIX: mrr_amount was removed from stg_stripe__subscriptions (thin staging).
-- MRR computation (unit_amount * quantity / 100.0) now lives here
-- as per best practice: business logic belongs in Intermediate, not Staging.
-- =============================================================================

with subscriptions as (
    select * from {{ ref('stg_stripe__subscriptions') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

-- Compute MRR in the domain layer (not staging)
subscriptions_with_mrr as (
    select
        *,
        -- Refund/credit case guard: unit_amount can be negative in Stripe
        case
            when unit_amount > 0
            then (unit_amount * quantity) / 100.0
            else 0
        end                                             as mrr_amount
    from subscriptions
),

final as (
    select
        s.workspace_id,
        sp.account_id,
        sp.workspace_name,

        -- Active MRR: only subscriptions currently paying
        sum(
            case when s.subscription_status = 'active'
            then s.mrr_amount else 0 end
        )                                               as active_mrr,

        -- Total MRR: includes trialing (potential revenue signal)
        sum(s.mrr_amount)                               as total_mrr,

        -- Seat utilization data (expansion blind spot)
        sum(s.seats_used)                               as seats_used,

        -- Silent Churn Signal: payment failed but not yet canceled
        max(
            case when s.subscription_status = 'past_due' then 1 else 0 end
        )                                               as is_payment_failing,

        -- Cancel intent: scheduled to cancel at period end
        max(
            case when s.is_cancel_at_period_end then 1 else 0 end
        )                                               as is_churning_soon,

        max(s.subscription_status)                      as latest_subscription_status,
        max(s.plan_id)                                  as current_plan,

        -- Payment classification
        case
            when sum(s.mrr_amount) > 0 then 'paying'
            else 'non_paying'
        end                                             as payment_status

    from subscriptions_with_mrr s
    left join spine sp on s.workspace_id = sp.internal_workspace_id
    group by 1, 2, 3
)

select * from final
