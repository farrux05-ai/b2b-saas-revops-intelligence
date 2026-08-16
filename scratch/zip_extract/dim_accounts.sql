{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: dim_accounts
-- MART: core
-- GRAIN: one row per account_id
--
-- QOIDA: Bu yerda yangi biznes mantiq YO'Q.
--        int_accounts_scored dan faqat SELECT + rename.
--        Yagona ruxsat etilgan hisob: arr = mrr * 12
--
-- O'ZGARISHLAR:
--   Barcha hisob-kitoblar int qatlamiga ko'chirildi.
--   is_low_engagement → int_product_aggregated dan keladi.
--   account_segment   → int_icp_scoring dan keladi.
--   health_reason     → int_accounts_scored dan keladi.
-- =============================================================================

with scored as (
    select * from {{ ref('int_accounts_scored') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    account_id,
    hubspot_company_id,
    internal_workspace_id,
    domain,
    workspace_name,
    company_name,
    industry,
    employee_count,
    utm_source,
    utm_campaign,
    lifecycle_stage,

    -- ── Workspace sanalar ─────────────────────────────────────────────────
    seat_limit,
    workspace_plan,
    created_at                                          as workspace_created_at,
    trial_started_at,
    trial_ended_at,
    converted_at,

    -- ── Revenue ───────────────────────────────────────────────────────────
    mrr,
    active_mrr,
    mrr * 12                                            as arr,      -- yagona ruxsat etilgan mart hisob
    latest_subscription_status                          as subscription_status,
    current_plan,
    current_period_start_at,
    current_period_end_at,
    first_payment_at,

    -- ── Segmentatsiya (int_icp_scoring dan) ──────────────────────────────
    account_segment,
    icp_score,
    icp_tier,

    -- ── Seat utilization ──────────────────────────────────────────────────
    seats_purchased,
    seats_used,
    seat_utilization_pct,
    is_ready_for_upsell,
    is_downsell_risk,

    -- ── Churn sinyallari ──────────────────────────────────────────────────
    is_payment_failing,
    is_churning_soon,
    is_low_engagement,
    is_trial_at_risk,
    payment_failure_category,

    -- ── Health scoring (int_accounts_scored dan) ─────────────────────────
    health_status,
    health_reason,
    mrr_at_risk,

    -- ── CRM / Sales ───────────────────────────────────────────────────────
    open_deals_count,
    won_deals_count,
    lifetime_revenue,
    last_won_date,
    stale_deals_count,
    avg_days_to_close_won,
    weighted_pipeline_value,
    crm_total_activities,
    crm_last_engagement_at,

    -- ── Support ───────────────────────────────────────────────────────────
    total_tickets,
    open_tickets,
    high_priority_tickets,
    avg_resolution_hours,
    last_ticket_at,

    -- ── Product ───────────────────────────────────────────────────────────
    is_pql,
    has_connected_git,
    has_started_sprint,
    total_product_events,
    last_activity_at,
    total_users,
    activated_users,
    active_users_last_30d,
    activation_rate,

    -- ── Audit ─────────────────────────────────────────────────────────────
    current_timestamp                                   as last_updated_at

from scored
