{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_lead_funnel
-- MART: marketing
-- GRAIN: one row per hubspot_company_id (lead)
--
-- AUDITORIYA: Marketing jamoasi — funnel tahlil, MQL sifat, kampaniya ROI.
--
-- QOIDA: stg_hubspot__companies dan to'g'ri olish — ruxsat etilgan istisno.
--        Sabab: bu mart HubSpot lead funnel ni ko'rsatadi.
--        Ba'zi leadlar hali workspace ochmagan (crm-only) →
--        int_accounts_joined da bo'lmasligi mumkin.
--        dim_accounts LEFT JOIN: convert bo'lgan leadlar uchun MRR ko'rsatiladi.
-- =============================================================================

with companies as (
    select * from {{ ref('stg_hubspot__companies') }}
),

accounts as (
    select
        hubspot_company_id,
        account_id,
        mrr,
        subscription_status,
        is_pql,
        total_product_events
    from {{ ref('dim_accounts') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    c.hubspot_company_id,
    a.account_id,
    c.company_name,
    c.domain,
    c.industry,
    c.employee_count,

    -- ── Funnel pozitsiya ──────────────────────────────────────────────────
    c.lifecycle_stage,
    c.lead_status,

    -- ── Konversiya flaglari ───────────────────────────────────────────────
    c.lifecycle_stage = 'customer'                      as is_customer,
    c.lifecycle_stage in (
        'salesqualifiedlead', 'opportunity', 'customer'
    )                                                   as is_sql_or_beyond,
    c.lifecycle_stage in (
        'marketingqualifiedlead', 'salesqualifiedlead',
        'opportunity', 'customer'
    )                                                   as is_mql_or_beyond,

    -- ── PLG overlay ───────────────────────────────────────────────────────
    coalesce(a.is_pql, false)                           as is_pql,
    coalesce(a.total_product_events, 0)                 as product_events_count,

    -- ── Revenue (faqat convert bo'lganlar uchun) ─────────────────────────
    coalesce(a.mrr, 0)                                  as current_mrr,
    a.subscription_status,

    -- ── CRM vaqt ──────────────────────────────────────────────────────────
    c.created_at                                        as became_lead_at,
    c.updated_at                                        as last_crm_activity_at,

    -- ── Lead yoshi ────────────────────────────────────────────────────────
    datediff('day', cast(c.created_at as date), current_date)
                                                        as lead_age_days

from companies c
left join accounts a on c.hubspot_company_id = a.hubspot_company_id
