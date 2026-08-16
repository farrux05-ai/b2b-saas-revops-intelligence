{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_crm_aggregated
-- LAYER: 2_domains
-- GRAIN: one row per hubspot_company_id
--
-- OLDINGI MODELLAR (2 ta) → BITTA MODEL:
--   int_sales_aggregated  → deals agregatsiya
--   (engagements mart da edi) → activities agregatsiya
--
-- MAS'ULIYAT:
--   HubSpot ning 2 ta jadvalidan (deals, engagements)
--   company darajasida barcha CRM metrikalarini hisoblaydi.
--   Pipeline velocity sinyallari (stale, days_to_close) bu yerda.
-- =============================================================================

with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

engagements as (
    select * from {{ ref('stg_hubspot__engagements') }}
),

deal_metrics as (
    select
        hubspot_company_id,

        -- Hajm
        count(hubspot_deal_id)                          as total_deals_created,

        -- Ochiq pipeline
        count(case
            when deal_stage not in ('closedwon', 'closedlost')
            then hubspot_deal_id end)                   as open_deals_count,

        -- Yutilgan bitimlar
        count(case
            when deal_stage = 'closedwon'
            then hubspot_deal_id end)                   as won_deals_count,

        -- Yo'qotilgan bitimlar
        count(case
            when deal_stage = 'closedlost'
            then hubspot_deal_id end)                   as lost_deals_count,

        -- Daromad
        coalesce(sum(case
            when deal_stage = 'closedwon'
            then amount else 0 end), 0)                 as lifetime_revenue,

        -- Oxirgi g'alaba sanasi
        max(case
            when deal_stage = 'closedwon'
            then closed_at end)                         as last_won_date,

        -- Pipeline velocity sinyallari (oldin fct_pipeline da edi)
        -- Eskirgan bitimlar: 90 kundan ko'p ochiq qolgan
        count(case
            when deal_stage not in ('closedwon', 'closedlost')
             and datediff('day', created_at, current_timestamp) > 90
            then hubspot_deal_id end)                   as stale_deals_count,

        -- O'rtacha yopilish vaqti (faqat yutilgan bitimlar uchun)
        avg(case
            when deal_stage = 'closedwon'
             and closed_at is not null
             and closed_at > created_at
            then datediff('day', created_at, closed_at)
        end)                                            as avg_days_to_close_won,

        -- Og'irlik bo'yicha pipeline qiymati
        coalesce(sum(case
            when deal_stage not in ('closedwon', 'closedlost')
            then coalesce(amount, 0) * coalesce(probability, 0) / 100.0
            else 0 end), 0)                             as weighted_pipeline_value

    from deals
    where hubspot_company_id is not null
    group by 1
),

engagement_metrics as (
    select
        hubspot_company_id,

        -- Umumiy faollik
        count(hubspot_engagement_id)                    as total_activities,

        -- Tur bo'yicha
        count(case when engagement_type = 'CALL'
            then hubspot_engagement_id end)             as call_count,
        count(case when engagement_type = 'EMAIL'
            then hubspot_engagement_id end)             as email_count,
        count(case when engagement_type = 'MEETING'
            then hubspot_engagement_id end)             as meeting_count,

        -- Oxirgi aloqa
        max(created_at)                                 as last_engagement_at

    from engagements
    where hubspot_company_id is not null
    group by 1
)

-- FULL OUTER JOIN: deals bor, engagement yo'q holatni ham qamrab oladi
select
    coalesce(d.hubspot_company_id,
             e.hubspot_company_id)                      as hubspot_company_id,

    -- Deal metrics
    coalesce(d.total_deals_created, 0)                  as total_deals_created,
    coalesce(d.open_deals_count, 0)                     as open_deals_count,
    coalesce(d.won_deals_count, 0)                      as won_deals_count,
    coalesce(d.lost_deals_count, 0)                     as lost_deals_count,
    coalesce(d.lifetime_revenue, 0)                     as lifetime_revenue,
    d.last_won_date,
    coalesce(d.stale_deals_count, 0)                    as stale_deals_count,
    d.avg_days_to_close_won,
    coalesce(d.weighted_pipeline_value, 0)              as weighted_pipeline_value,

    -- Engagement metrics
    coalesce(e.total_activities, 0)                     as total_activities,
    coalesce(e.call_count, 0)                           as call_count,
    coalesce(e.email_count, 0)                          as email_count,
    coalesce(e.meeting_count, 0)                        as meeting_count,
    e.last_engagement_at

from deal_metrics d
full outer join engagement_metrics e
    on d.hubspot_company_id = e.hubspot_company_id
