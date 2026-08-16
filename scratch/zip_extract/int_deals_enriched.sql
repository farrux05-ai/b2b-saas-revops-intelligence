{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_deals_enriched
-- LAYER: 2_domains
-- GRAIN: one row per hubspot_deal_id
--
-- YANGI MODEL — oldin mavjud emas edi.
-- Sabab: fct_pipeline stg_hubspot__deals ga to'g'ridan-to'g'ri murojaat qilardi.
--        Mart STG ni bilmasligi kerak (antipattern #13).
--
-- MAS'ULIYAT:
--   Deal-level ma'lumotni account context bilan boyitadi.
--   fct_pipeline shu modeldan oladi.
--   int_crm_aggregated dan farqi: bu deal-level (aggregatsiya yo'q).
-- =============================================================================

with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

-- Account context uchun backbone
accounts as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        domain
    from {{ ref('int_accounts_joined') }}
),

final as (
    select
        -- Deal identity
        d.hubspot_deal_id,
        d.hubspot_company_id,
        d.deal_name,
        d.pipeline,
        d.deal_stage,

        -- Financials
        coalesce(d.amount, 0)                           as amount,
        coalesce(d.probability, 0)                      as probability,
        -- Og'irlik bo'yicha qiymat (oldin fct_pipeline da edi)
        coalesce(d.amount, 0)
            * coalesce(d.probability, 0) / 100.0        as weighted_amount,

        -- Status flaglar (oldin fct_pipeline da edi)
        d.deal_stage = 'closedwon'                      as is_won,
        d.deal_stage = 'closedlost'                     as is_lost,
        d.deal_stage not in ('closedwon', 'closedlost') as is_open,

        -- Vaqt metrikалари (oldin fct_pipeline da edi)
        d.created_at,
        d.closed_at,

        case
            when d.closed_at is not null
             and d.closed_at > d.created_at
            then datediff('day', d.created_at, d.closed_at)
        end                                             as days_to_close,

        case
            when d.deal_stage not in ('closedwon', 'closedlost')
            then datediff('day', d.created_at, current_timestamp)
        end                                             as days_open,

        -- Eskirgan bitim sinyal (oldin fct_pipeline da edi)
        (d.deal_stage not in ('closedwon', 'closedlost')
         and datediff('day', d.created_at, current_timestamp) > 90
        )                                               as is_stale,

        -- Yosh bo'yicha kategoriya (oldin fct_pipeline da edi)
        case
            when d.deal_stage in ('closedwon', 'closedlost') then 'Closed'
            when datediff('day', d.created_at, current_timestamp) <= 30  then '0-30 days'
            when datediff('day', d.created_at, current_timestamp) <= 60  then '31-60 days'
            when datediff('day', d.created_at, current_timestamp) <= 90  then '61-90 days'
            else '90+ days (Stale)'
        end                                             as deal_age_bucket,

        -- Account context (int_accounts_joined dan)
        a.account_id,
        a.workspace_name,
        a.domain

    from deals d
    left join accounts a on d.hubspot_company_id = a.hubspot_company_id
)

select * from final
