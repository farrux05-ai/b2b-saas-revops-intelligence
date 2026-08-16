{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_mrr_waterfall
-- MART: finance
-- GRAIN: one row per account_id × month_date
-- MATERIALIZED: table — fct_retention_cohorts va fct_arr_movements yuqori
--               tezlikda so'raydi, view bo'lsa har safar date spine qayta ishlaydi
--
-- AUDITORIYA: Finance + Investor — MRR waterfall, NRR/GRR hisoblash.
--
-- QOIDA: Date spine + LAG window funksiyasi — bu mart da qoladi.
--        Sabab: bu finance-specific hisob-kitob (investor reporting).
--        INT ga olib o'tish mantiqsiz — boshqa jamoalar ishlatmaydi.
--
-- O'ZGARISH:
--   int_subscriptions_enriched → int_billing_aggregated
--   current_period_start/end_at int_billing_aggregated da bor
-- =============================================================================

-- Qadam 1: Account spine (int_accounts_joined dan bir marta)
with spine as (
    select
        account_id,
        internal_workspace_id                           as workspace_id,
        workspace_name
    from {{ ref('int_accounts_joined') }}
    where internal_workspace_id is not null
),

-- Qadam 2: Billing dan MRR va period sanalar
billing as (
    select
        b.workspace_id,
        s.account_id,
        s.workspace_name,
        b.total_mrr                                     as mrr_amount,
        b.latest_subscription_status                    as subscription_status,
        b.current_period_start_at,
        b.current_period_end_at,
        b.first_payment_at                              as created_at
    from {{ ref('int_billing_aggregated') }} b
    inner join spine s on b.workspace_id = s.workspace_id
),

-- Qadam 3: Date spine (oxirgi 2 yil)
months as (
    select cast(date_month as date) as month_date
    from (
        {{ dbt_utils.date_spine(
            datepart="month",
            start_date="cast(date_trunc('year', current_date - interval '2 years') as date)",
            end_date="cast(date_trunc('month', current_date + interval '1 month') as date)"
        ) }}
    )
),

-- Qadam 4: Har account uchun birinchi aktiv oy
accounts_first_month as (
    select
        account_id,
        workspace_name,
        cast(date_trunc('month', min(created_at)) as date) as first_active_month
    from billing
    group by 1, 2
),

-- Qadam 5: Account × Month spine
account_month_spine as (
    select
        a.account_id,
        a.workspace_name,
        m.month_date
    from accounts_first_month a
    cross join months m
    where m.month_date >= a.first_active_month
),

-- Qadam 6: Har oy uchun haqiqiy MRR
-- period_start ≤ month ≤ period_end → to'g'ri oy attribution
monthly_mrr as (
    select
        b.account_id,
        m.month_date,
        sum(case
            when b.subscription_status in ('active', 'trialing')
            then b.mrr_amount else 0
        end)                                            as mrr,
        sum(case
            when b.subscription_status = 'past_due'
            then b.mrr_amount else 0
        end)                                            as at_risk_mrr
    from billing b
    cross join months m
    where cast(date_trunc('month', b.current_period_start_at) as date) <= m.month_date
      and cast(date_trunc('month', b.current_period_end_at) as date)   >= m.month_date
      and b.subscription_status in ('active', 'trialing', 'past_due')
    group by 1, 2
),

-- Qadam 7: Spine + MRR + LAG (oldingi oy)
mrr_history as (
    select
        ams.account_id,
        ams.workspace_name,
        ams.month_date,
        coalesce(mm.mrr, 0)                             as mrr,
        coalesce(mm.at_risk_mrr, 0)                     as at_risk_mrr,
        coalesce(
            lag(coalesce(mm.mrr, 0)) over (
                partition by ams.account_id
                order by ams.month_date
            ), 0
        )                                               as previous_month_mrr
    from account_month_spine ams
    left join monthly_mrr mm
        on ams.account_id = mm.account_id
        and ams.month_date = mm.month_date
),

-- Qadam 8: MRR Waterfall klassifikatsiya
final as (
    select
        {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }}
                                                        as waterfall_id,
        account_id,
        workspace_name,
        month_date,
        mrr,
        at_risk_mrr,
        previous_month_mrr,
        mrr - previous_month_mrr                        as mrr_change_amount,

        case
            -- Qaytib kelgan (oldin churned bo'lgan)
            when mrr > 0
             and previous_month_mrr = 0
             and exists (
                 select 1 from mrr_history h2
                 where h2.account_id = mrr_history.account_id
                   and h2.month_date < mrr_history.month_date
                   and h2.mrr > 0
             )                                          then 'resurrection'
            -- Yangi account
            when mrr > 0
             and previous_month_mrr = 0                 then 'new'
            -- Ko'proq to'layapti
            when mrr > previous_month_mrr
             and previous_month_mrr > 0                 then 'expansion'
            -- Kamroq to'layapti (lekin nol emas)
            when mrr < previous_month_mrr
             and mrr > 0                                then 'contraction'
            -- Nolga tushdi
            when mrr = 0
             and previous_month_mrr > 0                 then 'churn'
            -- O'zgarmadi
            else 'retained'
        end                                             as mrr_movement_type

    from mrr_history
    -- Ikki tomon ham nol bo'lgan oylarni chiqarib tashlash
    where mrr > 0 or previous_month_mrr > 0
)

select * from final
