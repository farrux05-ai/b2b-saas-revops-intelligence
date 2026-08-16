{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_subscriptions
-- MART: finance
-- GRAIN: one row per workspace_id (active subscription snapshot)
--
-- AUDITORIYA: Finance jamoasi — MRR/ARR, plan mix, churn intent.
--
-- O'ZGARISH:
--   int_subscriptions_enriched → int_billing_aggregated
--   is_upsell_candidate, is_downsell_risk → int_billing_aggregated dan keladi
--   (oldin bu yerda hisoblardi)
--   fct_subscriptions endi workspace darajasida (Stripe subscription emas).
--   Sabab: int_billing_aggregated workspace grain da.
-- =============================================================================

with billing as (
    select * from {{ ref('int_billing_aggregated') }}
),

spine as (
    select
        account_id,
        internal_workspace_id                           as workspace_id,
        workspace_name,
        domain
    from {{ ref('int_accounts_joined') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    b.workspace_id,
    b.customer_id,
    s.account_id,
    s.workspace_name,
    s.domain,

    -- ── Plan ma'lumotlari ─────────────────────────────────────────────────
    b.latest_subscription_status                        as subscription_status,
    b.current_plan                                      as plan_id,

    -- ── Revenue ───────────────────────────────────────────────────────────
    b.total_mrr                                         as mrr_amount,
    b.total_mrr * 12                                    as arr_amount,
    b.active_mrr,

    -- ── Seat utilization ──────────────────────────────────────────────────
    b.seats_purchased,
    b.seats_used,
    b.seat_utilization_pct,

    -- ── Expansion / Contraction sinyallari (int_billing_aggregated dan) ──
    b.is_upsell_candidate,       -- oldin bu yerda hisoblardi
    b.is_downsell_risk,          -- oldin bu yerda hisoblardi

    -- ── Status flaglar ────────────────────────────────────────────────────
    b.latest_subscription_status = 'active'             as is_active,
    b.latest_subscription_status = 'trialing'           as is_trialing,
    b.latest_subscription_status = 'past_due'           as is_past_due,
    b.latest_subscription_status = 'canceled'           as is_canceled,
    b.is_churning_soon,

    -- ── Billing period ────────────────────────────────────────────────────
    b.current_period_start_at,
    b.current_period_end_at,
    b.trial_end_at,
    b.first_payment_at

from billing b
left join spine s on b.workspace_id = s.workspace_id
