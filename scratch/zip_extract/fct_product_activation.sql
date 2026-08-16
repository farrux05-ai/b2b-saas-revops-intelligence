{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_product_activation
-- MART: product
-- GRAIN: one row per workspace_id
--
-- AUDITORIYA: Product jamoasi — activation funnel, PLG tahlil, onboarding.
--
-- O'ZGARISH:
--   activation_rate         → int_product_aggregated dan keladi (oldin bu yerda edi)
--   is_trial_expired        → int_billing_aggregated dan keladi (oldin bu yerda edi)
--   total_users, activated  → int_product_aggregated dan keladi (oldin int_users_joined edi)
--   Bu mart endi faqat dim_accounts + int_product_aggregated dan SELECT qiladi.
-- =============================================================================

with accounts as (
    select
        account_id,
        internal_workspace_id                           as workspace_id,
        workspace_name,
        domain,
        account_segment,
        current_plan,
        mrr,
        subscription_status,
        seats_purchased,
        seats_used,
        seat_utilization_pct,
        is_ready_for_upsell,
        seat_limit,
        workspace_created_at,
        trial_started_at,
        trial_ended_at,
        converted_at,
        is_trial_at_risk
    from {{ ref('dim_accounts') }}
),

product as (
    select * from {{ ref('int_product_aggregated') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    a.workspace_id,
    a.account_id,
    a.workspace_name,
    a.domain,
    a.account_segment,
    a.current_plan,

    -- ── Revenue context ───────────────────────────────────────────────────
    a.mrr,
    a.subscription_status,

    -- ── User metrikалари (int_product_aggregated dan) ─────────────────────
    p.total_users,
    p.activated_users,
    p.active_users_last_30d,
    p.activation_rate,               -- oldin bu yerda hisoblardi

    -- ── Seat utilization ──────────────────────────────────────────────────
    a.seats_purchased,
    a.seats_used,
    a.seat_utilization_pct,
    a.is_ready_for_upsell,
    a.seat_limit,

    -- ── PQL va activation sinyallari (int_product_aggregated dan) ────────
    p.is_pql,
    p.has_connected_git,
    p.has_started_sprint,
    p.has_used_ai_prioritization,
    p.total_product_events,
    p.last_activity_at,
    p.is_low_engagement,

    -- ── Onboarding sanalar ────────────────────────────────────────────────
    a.workspace_created_at,
    a.trial_started_at,
    a.trial_ended_at,
    a.converted_at,

    -- ── Konversiya flaglari ───────────────────────────────────────────────
    a.converted_at is not null                          as is_converted,
    a.is_trial_at_risk,                                -- oldin bu yerda hisoblardi

    -- Trial tugagan, convert bo'lmagan
    -- (int_billing_aggregated da trial_end_at bor, shu yerda sodda hisob)
    case
        when a.trial_ended_at is not null
         and a.trial_ended_at < current_timestamp
         and a.converted_at is null
        then true else false
    end                                                 as is_trial_expired_no_convert

from accounts a
left join product p on a.workspace_id = p.workspace_id
