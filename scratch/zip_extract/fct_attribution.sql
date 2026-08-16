{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_attribution
-- MART: marketing
-- GRAIN: one row per account_id (first-touch attribution)
--
-- AUDITORIYA: Marketing jamoasi — kanal ROI, budget taqsimlash.
--
-- O'ZGARISH:
--   int_sales_aggregated → int_crm_aggregated (model o'zgargan nomi).
-- =============================================================================

with accounts as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        utm_source,
        utm_campaign,
        mrr,
        lifetime_revenue,
        workspace_created_at
    from {{ ref('dim_accounts') }}
),

crm as (
    select
        hubspot_company_id,
        won_deals_count,
        total_activities
    from {{ ref('int_crm_aggregated') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    a.account_id,
    a.workspace_name,

    -- ── Attribution (HubSpot UTM dan) ────────────────────────────────────
    a.utm_source                                        as acquisition_channel,
    a.utm_campaign                                      as first_touch_campaign,

    -- ── Revenue metrikалари ───────────────────────────────────────────────
    a.mrr,
    a.lifetime_revenue,

    -- ── Deal metrikалари ──────────────────────────────────────────────────
    coalesce(c.won_deals_count, 0)                      as won_deals_count,
    coalesce(c.total_activities, 0)                     as total_crm_activities,

    -- ── Vaqt ──────────────────────────────────────────────────────────────
    cast(a.workspace_created_at as date)                as account_created_at

from accounts a
left join crm c on a.hubspot_company_id = c.hubspot_company_id
where a.hubspot_company_id is not null
