{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: int_accounts_integrated
-- LAYER: 3_integration (Consolidated Account 360 View)
-- GRAIN: One row per account_id
-- MATERIALIZATION: Table (heavily queried by downstream marts)
--
-- BUSINESS RESPONSIBILITY:
--   Consolidates all domain aggregations onto the global Account Spine (int_accounts_joined).
--   Serves as the single source of truth ("Account 360") for all RevOps domains:
--     - Billing Domain (Stripe active MRR, seat utilization, churn signals)
--     - CRM Domain (HubSpot pipeline velocity, won/lost deals, activities)
--     - Support Domain (Zendesk open tickets, resolution hours, escalations)
--     - Product Domain (PostHog event volume, PQL status, user activation, low engagement)
--     - ICP Scoring (Enterprise / Mid-Market segmentation, ICP fit tier)
-- =============================================================================

with spine as (
    -- Backbone: all accounts (workspace-linked + crm-only leads)
    select * from {{ ref('int_accounts_joined') }}
),

workspaces as (
    -- Product workspace metadata
    select
        workspace_id,
        seat_limit,
        plan,
        created_at,
        trial_started_at,
        trial_ended_at,
        converted_at
    from {{ ref('stg_internal__workspaces') }}
),

hubspot as (
    -- CRM company metadata & attribution
    select
        hubspot_company_id,
        company_name,
        industry,
        utm_source,
        utm_campaign,
        lifecycle_stage,
        employee_count
    from {{ ref('stg_hubspot__companies') }}
),

billing as (
    -- Stripe billing, MRR, churn signals, seat utilization
    select * from {{ ref('int_billing_aggregated') }}
),

crm as (
    -- HubSpot deals & engagement activities
    select * from {{ ref('int_crm_aggregated') }}
),

support as (
    -- Zendesk support tickets & resolution metrics
    select * from {{ ref('int_support_aggregated') }}
),

product as (
    -- PostHog events, PQL signals, user activation, and low engagement flags
    select * from {{ ref('int_product_aggregated') }}
),

icp as (
    -- ICP scoring & ARR account segmentation
    select * from {{ ref('int_icp_scoring') }}
)

select
    -- ── Identity & Account Backbone ──────────────────────────────────────
    s.account_id,
    s.hubspot_company_id,
    s.internal_workspace_id,
    s.workspace_name,
    s.domain,

    -- ── Workspace Lifecycle & Limits ──────────────────────────────────────
    w.seat_limit,
    w.plan                                              as workspace_plan,
    w.created_at,
    w.trial_started_at,
    w.trial_ended_at,
    w.converted_at,

    -- ── CRM Metadata & Firmographics ─────────────────────────────────────
    h.company_name,
    h.industry,
    h.utm_source,
    h.utm_campaign,
    h.lifecycle_stage,
    h.employee_count,

    -- ── Revenue & Billing Metrics (Billing Domain) ─────────────────────────
    coalesce(b.active_mrr, 0)                           as active_mrr,
    coalesce(b.total_mrr, 0)                            as mrr,
    b.latest_subscription_status,
    b.current_plan,
    b.trial_end_at,
    b.current_period_start_at,
    b.current_period_end_at,

    -- ── Churn Risk Signals (Billing Domain) ──────────────────────────────
    coalesce(b.is_payment_failing, 0)                   as is_payment_failing,
    coalesce(b.is_churning_soon, 0)                     as is_churning_soon,
    b.payment_failure_category,

    -- ── Seat Utilization & Expansion (Billing Domain) ─────────────────────
    coalesce(b.seats_purchased, 0)                      as seats_purchased,
    coalesce(b.seats_used, 0)                           as seats_used,
    coalesce(b.seat_utilization_pct, 0)                 as seat_utilization_pct,
    coalesce(b.is_upsell_candidate, false)              as is_ready_for_upsell,
    coalesce(b.is_downsell_risk, false)                 as is_downsell_risk,

    -- ── Trial Conversion Risk (Billing Domain) ───────────────────────────
    b.first_payment_at,
    coalesce(b.is_trial_at_risk, false)                 as is_trial_at_risk,

    -- ── CRM & Sales Pipeline (CRM Domain) ─────────────────────────────────
    coalesce(c.open_deals_count, 0)                     as open_deals_count,
    coalesce(c.won_deals_count, 0)                      as won_deals_count,
    coalesce(c.lifetime_revenue, 0)                     as lifetime_revenue,
    c.last_won_date,
    coalesce(c.stale_deals_count, 0)                    as stale_deals_count,
    c.avg_days_to_close_won,
    coalesce(c.weighted_pipeline_value, 0)              as weighted_pipeline_value,

    -- Sales Engagement Activities
    coalesce(c.total_activities, 0)                     as crm_total_activities,
    c.last_engagement_at                                as crm_last_engagement_at,

    -- ── Support Health (Support Domain) ───────────────────────────────────
    coalesce(sp.total_tickets, 0)                       as total_tickets,
    coalesce(sp.open_tickets, 0)                        as open_tickets,
    coalesce(sp.high_priority_tickets, 0)               as high_priority_tickets,
    sp.avg_resolution_hours,
    sp.last_ticket_at,

    -- ── Product Usage & PQL Signals (Product Domain) ─────────────────────
    coalesce(p.total_product_events, 0)                 as total_product_events,
    p.last_activity_at,
    coalesce(p.has_connected_git, false)                as has_connected_git,
    coalesce(p.has_started_sprint, false)               as has_started_sprint,
    coalesce(p.is_pql, false)                           as is_pql,

    -- User Demographics & Adoption (Product Domain)
    coalesce(p.total_users, 0)                          as total_users,
    coalesce(p.activated_users, 0)                      as activated_users,
    coalesce(p.active_users_last_30d, 0)                as active_users_last_30d,
    coalesce(p.activation_rate, 0)                      as activation_rate,

    -- ── Low Engagement Risk Signal (Product Domain) ──────────────────────
    coalesce(p.is_low_engagement, true)                 as is_low_engagement,

    -- ── ICP Scoring & Segmentation (ICP Domain) ──────────────────────────
    i.account_segment,
    i.icp_score,
    i.icp_tier

from spine s
left join workspaces w  on s.internal_workspace_id = w.workspace_id
left join hubspot h     on s.hubspot_company_id = h.hubspot_company_id
left join billing b     on s.internal_workspace_id = b.workspace_id
left join crm c         on s.hubspot_company_id = c.hubspot_company_id
left join support sp    on s.account_id = sp.account_id
left join product p     on s.internal_workspace_id = p.workspace_id
left join icp i         on s.account_id = i.account_id
