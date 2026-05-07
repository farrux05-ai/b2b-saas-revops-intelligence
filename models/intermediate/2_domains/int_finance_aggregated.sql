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

user_counts as (
    select
        internal_workspace_id as workspace_id,
        count(internal_user_id) as actual_seats_used
    from {{ ref('int_users_joined') }}
    group by 1
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
        end                                             as mrr_amount,
        
        -- Identify the latest subscription for status/plan extraction
        row_number() over (
            partition by workspace_id 
            order by created_at desc
        )                                               as recency_rank
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

        -- Actual Seat utilization from internal DB (not purchased quantity)
        max(coalesce(uc.actual_seats_used, 0))           as seats_used,
        sum(s.seats_purchased)                          as seats_purchased,

        -- Silent Churn Signal: payment failed but not yet canceled
        max(
            case when s.subscription_status = 'past_due' then 1 else 0 end
        )                                               as is_payment_failing,

        -- Cancel intent: scheduled to cancel at period end
        max(
            case when s.is_cancel_at_period_end then 1 else 0 end
        )                                               as is_churning_soon,

        max(case when s.recency_rank = 1 then s.subscription_status end) as latest_subscription_status,
        max(case when s.recency_rank = 1 then s.plan_id end)            as current_plan,

        -- Payment classification
        case
            when sum(s.mrr_amount) > 0 then 'paying'
            else 'non_paying'
        end                                             as payment_status

    from subscriptions_with_mrr s
    left join spine sp   on s.workspace_id = sp.internal_workspace_id
    left join user_counts uc on s.workspace_id = uc.workspace_id
    group by 1, 2, 3
)

select * from final
