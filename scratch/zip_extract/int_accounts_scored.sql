{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_accounts_scored
-- LAYER: 3_integration
-- GRAIN: one row per account_id
--
-- O'ZGARISHLAR:
--   is_low_engagement → int_accounts_integrated dan keladi (oldin mart da edi)
--   health_reason → 3 ta churn sinyal to'liq qamrab olingan
--   mrr_at_risk → health_status dan derivatsiya qilingan (drift oldini olish)
--
-- SCORING TARTIBI (muhim — tartib noto'g'ri bo'lsa noto'g'ri natija):
--   Churned > Payment Failing > Support Critical >
--   Low Engagement > Expansion Target > Healthy
--
-- MAS'ULIYAT:
--   int_accounts_integrated ga health_status + health_reason + mrr_at_risk qo'shadi.
--   dim_accounts shu modeldan oladi.
-- =============================================================================

with master as (
    select * from {{ ref('int_accounts_integrated') }}
),

-- Qadam 1: health_reason hisoblash (aniq sabab — CS jamoasi uchun)
health_reasons as (
    select
        *,
        case
            -- 1. Churned: subscription bekor qilingan
            when latest_subscription_status = 'canceled'
                then 'Churned'

            -- 2. Payment Failing: silent churn (to'lov o'tmadi)
            when is_payment_failing = 1
                then 'Payment Failing'

            -- 3. Support Critical: ko'p ochiq ticket = muammo bor
            when open_tickets > 5
                then 'Support Critical'

            -- 4. Low Engagement: mahsulotdan foydalanmayapti
            -- is_low_engagement int_product_aggregated da hisoblangan
            -- (NULL guard u yerda allaqachon bor)
            when is_low_engagement = true
                then 'Low Engagement'

            -- 5. Expansion Target: ochiq deal bor + to'layapti
            when open_deals_count > 0
             and mrr > 0
                then 'Expansion Target'

            -- 6. Healthy: barcha sinyallar yaxshi
            else 'Healthy'
        end                                             as health_reason

    from master
),

-- Qadam 2: health_status + mrr_at_risk health_reason dan derivatsiya
-- Ikki xil CASE yozish o'rniga health_reason dan olinadi → drift yo'q
final as (
    select
        r.*,

        -- health_status: yuqori darajali holat (dashboardlar uchun)
        case
            when r.health_reason = 'Churned'
                then 'Churned'
            when r.health_reason in (
                'Payment Failing',
                'Support Critical',
                'Low Engagement')
                then 'At Risk'
            else 'Healthy'
        end                                             as health_status,

        -- mrr_at_risk: CS uchun moliyaviy ta'sir
        -- Churned emas + At Risk = xavf ostidagi MRR
        case
            when r.health_reason in (
                'Payment Failing',
                'Support Critical',
                'Low Engagement')
            then r.mrr
            else 0
        end                                             as mrr_at_risk

    from health_reasons r
)

select * from final
