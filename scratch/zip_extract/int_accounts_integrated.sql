{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: int_accounts_integrated
-- LAYER: 3_integration
-- GRAIN: one row per account_id
-- MATERIALIZED: table — mart lar ko'p so'raydi, view bo'lsa har safar qayta hisoblaydi
--
-- O'ZGARISHLAR:
--   int_finance_aggregated  → int_billing_aggregated (3 Stripe jadval birlashgan)
--   int_sales_aggregated    → int_crm_aggregated (deals + engagements birlashgan)
--   int_usage_aggregated    → int_product_aggregated (events + user stats + is_low_engagement)
--   is_payment_failing      → int_billing_aggregated dan keladi (oldin int_finance_aggregated)
--   is_churning_soon        → int_billing_aggregated dan keladi
--   is_low_engagement       → int_product_aggregated dan keladi (oldin mart da edi)
--   account_segment         → int_icp_scoring dan keladi (bir joyda hisoblangan)
--
-- MAS'ULIYAT:
--   Barcha domain aggregationlarni account spine ga birlashtiradi.
--   Bu model = "Account 360" — barcha jamoalar shu orqali ma'lumot oladi.
--   Yangi biznes mantiq QO'SHILMAYDI — faqat domain modellar birlashtiriladi.
-- =============================================================================

with spine as (
    -- Backbone: barcha accountlar (workspace + crm-only)
    select * from {{ ref('int_accounts_joined') }}
),

workspaces as (
    -- Workspace-specific ma'lumotlar (seat_limit, sanalar)
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
    -- CRM enrichment (utm, industry, company_name)
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
    -- Stripe: MRR, churn sinyallari, seat utilization
    -- int_billing_aggregated: workspace_id darajasida
    select * from {{ ref('int_billing_aggregated') }}
),

crm as (
    -- HubSpot: deals + engagements
    -- int_crm_aggregated: hubspot_company_id darajasida
    select * from {{ ref('int_crm_aggregated') }}
),

support as (
    -- Zendesk: tickets, resolution
    -- int_support_aggregated: account_id darajasida
    select * from {{ ref('int_support_aggregated') }}
),

product as (
    -- PostHog: events, PQL, activation, is_low_engagement
    -- int_product_aggregated: workspace_id darajasida
    select * from {{ ref('int_product_aggregated') }}
),

icp as (
    -- ICP scoring + account_segment
    -- int_icp_scoring: account_id darajasida
    select * from {{ ref('int_icp_scoring') }}
)

select
    -- ── Identity ─────────────────────────────────────────────────────────
    s.account_id,
    s.hubspot_company_id,
    s.internal_workspace_id,
    s.workspace_name,
    s.domain,

    -- ── Workspace sanalar va limitlar ────────────────────────────────────
    w.seat_limit,
    w.plan                                              as workspace_plan,
    w.created_at,
    w.trial_started_at,
    w.trial_ended_at,
    w.converted_at,

    -- ── CRM enrichment ───────────────────────────────────────────────────
    h.company_name,
    h.industry,
    h.utm_source,
    h.utm_campaign,
    h.lifecycle_stage,
    h.employee_count,

    -- ── Revenue (billing domain) ─────────────────────────────────────────
    coalesce(b.active_mrr, 0)                           as active_mrr,
    coalesce(b.total_mrr, 0)                            as mrr,
    b.latest_subscription_status,
    b.current_plan,
    b.trial_end_at,
    b.current_period_start_at,
    b.current_period_end_at,

    -- ── Churn sinyallari (billing domain) ───────────────────────────────
    coalesce(b.is_payment_failing, 0)                   as is_payment_failing,
    coalesce(b.is_churning_soon, 0)                     as is_churning_soon,
    b.payment_failure_category,

    -- ── Seat utilization (billing domain) ────────────────────────────────
    coalesce(b.seats_purchased, 0)                      as seats_purchased,
    coalesce(b.seats_used, 0)                           as seats_used,
    coalesce(b.seat_utilization_pct, 0)                 as seat_utilization_pct,
    coalesce(b.is_upsell_candidate, false)              as is_ready_for_upsell,
    coalesce(b.is_downsell_risk, false)                 as is_downsell_risk,

    -- ── Trial conversion (billing domain) ────────────────────────────────
    b.first_payment_at,
    coalesce(b.is_trial_at_risk, false)                 as is_trial_at_risk,

    -- ── CRM / Sales (crm domain) ─────────────────────────────────────────
    coalesce(c.open_deals_count, 0)                     as open_deals_count,
    coalesce(c.won_deals_count, 0)                      as won_deals_count,
    coalesce(c.lifetime_revenue, 0)                     as lifetime_revenue,
    c.last_won_date,
    coalesce(c.stale_deals_count, 0)                    as stale_deals_count,
    c.avg_days_to_close_won,
    coalesce(c.weighted_pipeline_value, 0)              as weighted_pipeline_value,

    -- Engagement (CRM faoliyat)
    coalesce(c.total_activities, 0)                     as crm_total_activities,
    c.last_engagement_at                                as crm_last_engagement_at,

    -- ── Support (support domain) ─────────────────────────────────────────
    coalesce(sp.total_tickets, 0)                       as total_tickets,
    coalesce(sp.open_tickets, 0)                        as open_tickets,
    coalesce(sp.high_priority_tickets, 0)               as high_priority_tickets,
    sp.avg_resolution_hours,
    sp.last_ticket_at,

    -- ── Product (product domain) ─────────────────────────────────────────
    coalesce(p.total_product_events, 0)                 as total_product_events,
    p.last_activity_at,
    coalesce(p.has_connected_git, false)                as has_connected_git,
    coalesce(p.has_started_sprint, false)               as has_started_sprint,
    coalesce(p.is_pql, false)                           as is_pql,

    -- User statistikasi (product domain dan)
    coalesce(p.total_users, 0)                          as total_users,
    coalesce(p.activated_users, 0)                      as activated_users,
    coalesce(p.active_users_last_30d, 0)                as active_users_last_30d,
    coalesce(p.activation_rate, 0)                      as activation_rate,

    -- ── Engagement churn sinyal (product domain) ─────────────────────────
    -- Oldin fct_accounts_health da CASE edi, endi int_product_aggregated da
    coalesce(p.is_low_engagement, true)                 as is_low_engagement,
    -- NULL guard: product domain yo'q account = hech qachon ishlatmagan = low engagement

    -- ── ICP scoring (icp domain) ─────────────────────────────────────────
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
