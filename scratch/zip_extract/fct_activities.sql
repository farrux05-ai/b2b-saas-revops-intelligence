{{
    config(
        materialized='incremental',
        unique_key='activity_id',
        incremental_strategy='merge',
        on_schema_change='sync_all_columns'
    )
}}

-- =============================================================================
-- MODEL: fct_activities
-- MART: sales
-- GRAIN: one row per hubspot_engagement_id
--
-- AUDITORIYA: Sales jamoasi — rep produktivligi, account engagement.
--
-- QOIDA: Bu mart stg_hubspot__engagements dan to'g'ri oladi.
--        Sabab: engagement-level (raw event) — int_crm_aggregated da
--        agregatsiya qilingan versiyasi bor, lekin bu yerda
--        row-level kerak (timestamp, owner, type).
--        Bu yagona ruxsat etilgan STG → MART to'g'ri yo'l.
--        (int_deals_enriched kabi deal-level model yaratish kerak emas,
--         chunki engagement lar dim_accounts ga join qilish uchun
--         int_crm_aggregated allaqachon bor.)
-- =============================================================================

with engagements as (
    select * from {{ ref('stg_hubspot__engagements') }}
    {% if is_incremental() %}
    -- 3 kun overlap: late-arriving records uchun
    where created_at >= (
        select max(activity_at) - interval '3 days'
        from {{ this }}
    )
    {% endif %}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    hubspot_engagement_id                               as activity_id,
    hubspot_company_id,
    owner_id,

    -- ── Dimensiyalar ──────────────────────────────────────────────────────
    engagement_type                                     as activity_type,

    -- ── Vaqt ──────────────────────────────────────────────────────────────
    created_at                                          as activity_at,
    cast(date_trunc('day', created_at) as date)         as activity_date

from engagements
where hubspot_company_id is not null
