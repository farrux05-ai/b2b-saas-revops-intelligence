{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_pipeline
-- MART: sales
-- GRAIN: one row per hubspot_deal_id
--
-- AUDITORIYA: Sales jamoasi — pipeline review, forecasting, rep performance.
--
-- O'ZGARISH:
--   stg_hubspot__deals → int_deals_enriched (mart STG bilmasligi kerak).
--   days_to_close, is_stale, deal_age_bucket, weighted_amount →
--   int_deals_enriched da hisoblangan (oldin bu yerda edi).
--   avg_won_days_to_close window funksiyasi — portfolio benchmark,
--   deal-level ma'no beradi, shu yerda qoladi (ruxsat etilgan istisno).
--   account health context → dim_accounts dan (health_status, mrr).
-- =============================================================================

with deals as (
    select * from {{ ref('int_deals_enriched') }}
),

-- Account context: health va MRR (sales uchun qo'shimcha signal)
accounts as (
    select
        account_id,
        account_segment,
        health_status,
        mrr                                             as account_mrr
    from {{ ref('dim_accounts') }}
)

select
    -- ── Deal identity ──────────────────────────────────────────────────────
    d.hubspot_deal_id,
    d.hubspot_company_id,
    d.account_id,
    d.workspace_name,
    d.domain,
    d.deal_name,

    -- ── Pipeline pozitsiya ────────────────────────────────────────────────
    d.pipeline,
    d.deal_stage,

    -- ── Moliyaviy (int_deals_enriched dan) ───────────────────────────────
    d.amount                                            as deal_amount,
    d.probability                                       as win_probability,
    d.weighted_amount,

    -- ── Status flaglar (int_deals_enriched dan) ───────────────────────────
    d.is_won,
    d.is_lost,
    d.is_open,
    d.is_stale,
    d.deal_age_bucket,

    -- ── Vaqt metrikалари (int_deals_enriched dan) ────────────────────────
    d.created_at,
    d.closed_at,
    d.days_to_close,
    d.days_open,

    -- ── Portfolio benchmark (window funksiya — ruxsat etilgan istisno) ───
    -- Bu mart da qoladi: har bir deal uchun portfolio o'rtachasini ko'rsatadi.
    -- INT ga olib o'tish ma'nosiz — har bir deal uchun bir xil qiymat.
    avg(case
        when d.is_won and d.days_to_close is not null
        then d.days_to_close
    end) over ()                                        as portfolio_avg_days_to_close,

    -- ── Account context (dim_accounts dan) ───────────────────────────────
    a.account_segment,
    a.health_status                                     as account_health_status,
    a.account_mrr

from deals d
left join accounts a on d.account_id = a.account_id
