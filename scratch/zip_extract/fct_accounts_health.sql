{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_accounts_health
-- MART: customer_success
-- GRAIN: one row per paying account
--
-- AUDITORIYA: CS jamoasi — churn prevention, QBR, prioritizatsiya.
--
-- O'ZGARISH:
--   is_low_engagement CASE olib tashlandi.
--   int_product_aggregated → int_accounts_integrated → int_accounts_scored
--   → dim_accounts orqali keladi.
--   Bu mart faqat dim_accounts dan SELECT qiladi + WHERE filter.
-- =============================================================================

with accounts as (
    select * from {{ ref('dim_accounts') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    account_id,
    domain,
    workspace_name,
    company_name,
    account_segment,
    current_plan,

    -- ── Revenue ───────────────────────────────────────────────────────────
    mrr,
    arr,
    mrr_at_risk,

    -- ── Health ────────────────────────────────────────────────────────────
    health_status,
    health_reason,
    subscription_status,

    -- ── Churn sinyallari (3 tur) ──────────────────────────────────────────
    is_payment_failing,      -- 1. Silent churn: to'lov o'tmadi
    is_churning_soon,        -- 2. Intent churn: bekor qilish rejalashtirilgan
    is_low_engagement,       -- 3. Usage churn: mahsulot ishlatilmayapti (INT dan)

    -- ── Support yuklamasi ─────────────────────────────────────────────────
    total_tickets,
    open_tickets,
    high_priority_tickets,
    avg_resolution_hours,
    last_ticket_at,

    -- ── Product faoliyati ─────────────────────────────────────────────────
    total_product_events,
    last_activity_at,
    is_pql,

    -- ── Expansion sinyallari ──────────────────────────────────────────────
    seats_purchased,
    seats_used,
    seat_utilization_pct,
    is_ready_for_upsell

from accounts
-- CS faqat billing ga kirgan accountlar bilan ishlaydi
where subscription_status is not null
