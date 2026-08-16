{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_trial_conversion
-- MART: product
-- GRAIN: one row per workspace_id (trialing yoki trial bo'lgan)
--
-- AUDITORIYA: Product + CS jamoasi — trial → paid konversiya tahlil.
--
-- O'ZGARISH:
--   int_subscriptions_enriched → int_billing_aggregated
--   int_payments_enriched      → int_billing_aggregated
--   is_at_risk_of_expiring     → int_billing_aggregated.is_trial_at_risk (oldin bu yerda edi)
--   time_to_convert_days       → first_payment_at asosida bu yerda hisoblanadi
--                               (workspace darajasida, subscription darajasida emas)
-- =============================================================================

with billing as (
    select * from {{ ref('int_billing_aggregated') }}
    -- Faqat trial bo'lgan yoki hozir trialing accountlar
    where latest_subscription_status = 'trialing'
       or trial_end_at is not null
),

spine as (
    select
        account_id,
        internal_workspace_id                           as workspace_id,
        workspace_name,
        domain
    from {{ ref('int_accounts_joined') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    b.workspace_id,
    b.customer_id,
    s.account_id,
    s.workspace_name,
    s.domain,

    -- ── Plan ──────────────────────────────────────────────────────────────
    b.current_plan                                      as plan_id,
    b.latest_subscription_status                        as subscription_status,

    -- ── Trial oyna ────────────────────────────────────────────────────────
    b.trial_end_at,
    b.current_period_start_at                           as trial_started_at,

    -- ── Konversiya ────────────────────────────────────────────────────────
    b.first_payment_at                                  as converted_at,

    -- Convert bo'ldimi?
    b.first_payment_at is not null                      as is_converted,

    -- Trial boshlanishidan birinchi to'lovgacha kun soni
    case
        when b.first_payment_at is not null
        then datediff('day',
            b.current_period_start_at,
            b.first_payment_at)
    end                                                 as time_to_convert_days,

    -- Trial qolgan kun (manfiy = allaqachon tugagan)
    case
        when b.trial_end_at is not null
        then datediff('day', current_timestamp, b.trial_end_at)
    end                                                 as trial_days_remaining,

    -- ── Risk sinyallari (int_billing_aggregated dan) ──────────────────────
    b.is_trial_at_risk                                  as is_at_risk_of_expiring,

    -- Tugagan, convert bo'lmagan
    case
        when b.trial_end_at is not null
         and b.trial_end_at < current_timestamp
         and b.first_payment_at is null
        then true else false
    end                                                 as is_expired_unconverted

from billing b
left join spine s on b.workspace_id = s.workspace_id
