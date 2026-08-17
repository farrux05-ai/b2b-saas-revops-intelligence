{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_billing_aggregated
-- LAYER: 2_domains (Domain Aggregations)
-- GRAIN: One row per workspace_id
--
-- CONSOLIDATION RATIONALE:
--   Consolidates 3 legacy domain models (int_subscriptions_enriched,
--   int_finance_aggregated, int_payments_enriched) into a single canonical
--   workspace-level billing domain model.
--
-- BUSINESS RESPONSIBILITY:
--   Aggregates Stripe raw entities (subscriptions, invoices, payments) alongside
--   internal seat usage at the workspace level.
--   Computes active MRR, churn risk indicators, seat utilization, trial conversion,
--   and payment failure categories.
--   Note: account_id is omitted here and resolved downstream in 3_integration.
--
-- FIX (2026-08, audit): active_mrr / total_mrr / seats_purchased used to be
-- computed with a blind SUM(...) across every subscription row a workspace
-- ever had (all historical statuses included), while every other field in
-- this model correctly isolated the CURRENT subscription via
-- recency_rank = 1. For any workspace with more than one subscription in
-- its history (plan upgrade/downgrade, cancel + resubscribe), that blind
-- SUM silently inflated MRR, ARR and seat counts. We now isolate the
-- current subscription once (current_subscription CTE) and use it
-- consistently for every "point-in-time" metric in this model.
-- Historical month-by-month MRR (for the waterfall) is handled separately
-- in int_mrr_monthly, which is sourced from Stripe invoices instead.
-- =============================================================================

with subscriptions as (
    select
        workspace_id,
        customer_id,
        subscription_id,
        subscription_status,
        plan_id,
        unit_amount,
        seats_purchased,
        is_cancel_at_period_end,
        created_at,
        current_period_start_at,
        current_period_end_at,
        trial_end_at,

        -- Calculate MRR: Monthly Recurring Revenue per subscription
        case
            when unit_amount > 0
            then unit_amount * seats_purchased
            else 0
        end                                             as mrr_amount,

        -- Identify latest subscription for workspace-level plan/status extraction
        row_number() over (
            partition by workspace_id
            order by created_at desc, subscription_id desc
        )                                               as recency_rank

    from {{ ref('stg_stripe__subscriptions') }}
),

-- FIX: The single source of truth for "what is this workspace's subscription
-- right now". Exactly one row per workspace_id.
current_subscription as (
    select *
    from subscriptions
    where recency_rank = 1
),

invoices as (
    select
        invoice_id,
        subscription_id,
        customer_id,
        invoice_status,
        amount_due,
        amount_paid,
        created_at
    from {{ ref('stg_stripe__invoices') }}
),

payments as (
    select
        p.payment_id,
        p.customer_id,
        p.invoice_id,
        p.payment_status,
        p.failure_code,
        p.amount,
        p.created_at,

        -- Categorize payment failure root cause for CS & Churn alerting
        case
            when p.failure_code in (
                'card_declined', 'expired_card', 'card_velocity_exceeded')
                then 'card_issue'
            when p.failure_code in (
                'insufficient_funds', 'balance_insufficient')
                then 'funds_issue'
            when p.failure_code in (
                'fraudulent', 'issuer_declined', 'stolen_card', 'lost_card')
                then 'fraud_risk'
            when p.failure_code is not null
                then 'other'
            else null
        end                                             as failure_category,

        p.failure_code is not null                      as is_failed

    from {{ ref('stg_stripe__payments') }} p
),

-- Track first successful payment per customer for trial conversion analytics
first_payments as (
    select
        customer_id,
        min(created_at)                                 as first_payment_at,
        count(*)                                        as successful_payments_count
    from payments
    where payment_status = 'succeeded'
    group by 1
),

-- Actual active seat counts from product database (internal DB)
user_seat_counts as (
    select
        internal_workspace_id                           as workspace_id,
        count(internal_user_id)                         as actual_seats_used
    from {{ ref('int_users_joined') }}
    group by 1
),

-- Determine worst payment failure category at workspace level (Severity: fraud > funds > card > other)
-- NOTE: intentionally matches against ALL historical subscription_ids (not just
-- current_subscription), because a failed payment can belong to a prior
-- subscription record while still being the correct "worst failure" signal
-- for the workspace today.
payment_failures as (
    select
        i.subscription_id,
        s.workspace_id,
        case max(case
            when p.failure_category = 'fraud_risk'  then 4
            when p.failure_category = 'funds_issue' then 3
            when p.failure_category = 'card_issue'  then 2
            when p.failure_category = 'other'       then 1
            else 0
        end)
            when 4 then 'fraud_risk'
            when 3 then 'funds_issue'
            when 2 then 'card_issue'
            when 1 then 'other'
            else null
        end                                             as worst_failure_category
    from payments p
    left join invoices i      on p.invoice_id = i.invoice_id
    left join subscriptions s on i.subscription_id = s.subscription_id
    where p.is_failed = true
      and s.workspace_id is not null
    group by i.subscription_id, s.workspace_id
),

-- Aggregate current-state billing metrics at the workspace grain.
-- FIX: current_subscription already has exactly 1 row per workspace_id, so
-- this is a plain join (no SUM/GROUP BY needed) — this is what removes the
-- history-inflation bug.
workspace_billing as (
    select
        cs.workspace_id,
        cs.customer_id,

        -- ── MRR Metrics (current subscription only) ─────────────────────
        case when cs.subscription_status = 'active'
            then cs.mrr_amount else 0 end               as active_mrr,
        case when cs.subscription_status != 'canceled'
            then cs.mrr_amount else 0 end               as total_mrr,

        -- ── Subscription Lifecycle State ────────────────────────────────
        cs.subscription_status                          as latest_subscription_status,
        cs.plan_id                                       as current_plan,
        cs.trial_end_at,
        cs.current_period_end_at,
        cs.current_period_start_at,

        -- ── Churn Risk Signals ──────────────────────────────────────────
        -- Silent Churn: Payment past due but subscription not yet canceled
        case when cs.subscription_status = 'past_due'
            then 1 else 0 end                           as is_payment_failing,
        -- Intentional Churn: User requested cancellation at period end
        case when cs.is_cancel_at_period_end
            then 1 else 0 end                           as is_churning_soon,

        -- ── Seat Utilization (current subscription only) ────────────────
        cs.seats_purchased,

        -- ── Conversion Metrics ──────────────────────────────────────────
        fp.first_payment_at,
        fp.successful_payments_count,

        -- ── Expansion & Contraction Signals ─────────────────────────────
        -- Upsell candidate: >= 90% seat utilization
        case
            when cs.seats_purchased > 0
             and coalesce(uc.actual_seats_used, 0)::float
                 / nullif(cs.seats_purchased, 0) >= 0.9
            then true else false
        end                                             as is_upsell_candidate,
        -- Downsell risk: < 30% seat utilization on multi-seat plans
        case
            when cs.seats_purchased > 1
             and coalesce(uc.actual_seats_used, 0)::float
                 / nullif(cs.seats_purchased, 0) < 0.3
            then true else false
        end                                             as is_downsell_risk,

        -- ── Trial Conversion Risk ───────────────────────────────────────
        -- Trial expiring within 3 days without a recorded payment
        case
            when cs.subscription_status = 'trialing'
             and cs.trial_end_at is not null
             and datediff('day', current_timestamp, cs.trial_end_at) between 0 and 3
             and fp.first_payment_at is null
            then true else false
        end                                             as is_trial_at_risk

    from current_subscription cs
    left join first_payments fp   on cs.customer_id = fp.customer_id
    left join user_seat_counts uc on cs.workspace_id = uc.workspace_id
)

select
    wb.workspace_id,
    wb.customer_id,

    -- MRR Metrics
    wb.active_mrr,
    wb.total_mrr,

    -- Subscription State
    wb.latest_subscription_status,
    wb.current_plan,
    wb.trial_end_at,
    wb.current_period_start_at,
    wb.current_period_end_at,

    -- Churn Signals
    wb.is_payment_failing,
    wb.is_churning_soon,

    -- Seat Utilization
    wb.seats_purchased,
    coalesce(uc.actual_seats_used, 0)                   as seats_used,
    case
        when wb.seats_purchased > 0
        then coalesce(uc.actual_seats_used, 0)::float
             / nullif(wb.seats_purchased, 0)
        else 0
    end                                                 as seat_utilization_pct,

    -- Expansion & Contraction Signals
    wb.is_upsell_candidate,
    wb.is_downsell_risk,

    -- Conversion & Trial Risk
    wb.first_payment_at,
    wb.successful_payments_count,
    wb.is_trial_at_risk,

    -- Payment Failure Categorization
    pf.worst_failure_category                           as payment_failure_category

from workspace_billing wb
left join user_seat_counts uc on wb.workspace_id = uc.workspace_id
left join payment_failures pf on wb.workspace_id = pf.workspace_id