{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: dim_accounts
-- MART: core
-- GRAIN: One row per account_id
--
-- BUSINESS CONTRACT:
--   Canonical Account 360 Dimension Model.
--   Performs SELECT + Column renaming from int_accounts_scored.
--   No heavy calculations permitted here except arr = mrr * 12.
--
-- SOURCE DATA FLOW:
--   All domain metrics (billing, crm, usage, support, icp scoring)
--   are pre-aggregated in int_accounts_integrated and scored in int_accounts_scored.
-- =============================================================================

with scored as (
    select * from {{ ref('int_accounts_scored') }}
)

select
    -- Identity & Metadata
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

    -- Workspace Timestamps & Configuration
    seat_limit,
    workspace_plan,
    created_at                                          as workspace_created_at,
    trial_started_at,
    trial_ended_at,
    converted_at,

    -- Financial / Revenue Metrics
    mrr,
    active_mrr,
    mrr * 12                                            as arr,
    latest_subscription_status                          as subscription_status,
    current_plan,
    current_period_start_at,
    current_period_end_at,
    first_payment_at,

    -- Account Segmentation (derived in int_icp_scoring)
    account_segment,
    icp_score,
    icp_tier,

    -- Seat Utilization & Capacity
    seats_purchased,
    seats_used,
    seat_utilization_pct,
    is_ready_for_upsell,
    is_downsell_risk,

    -- Churn Risk Indicators
    is_payment_failing,
    is_churning_soon,
    is_low_engagement,
    is_trial_at_risk,
    payment_failure_category,

    -- Multi-Signal Health Scoring (derived in int_accounts_scored)
    health_status,
    health_reason,
    mrr_at_risk,

    -- CRM & Sales Activity Summary
    open_deals_count,
    won_deals_count,
    lifetime_revenue,
    last_won_date,
    stale_deals_count,
    avg_days_to_close_won,
    weighted_pipeline_value,
    crm_total_activities,
    crm_last_engagement_at,

    -- Support Ticket Summary
    total_tickets,
    open_tickets,
    high_priority_tickets,
    avg_resolution_hours,
    last_ticket_at,

    -- Product Usage & Activation Milestones
    is_pql,
    has_connected_git,
    has_started_sprint,
    total_product_events,
    last_activity_at,
    total_users,
    activated_users,
    active_users_last_30d,
    activation_rate,

    -- Audit Column
    current_timestamp                                   as last_updated_at

from scored
