{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_billing_aggregated
-- LAYER: 2_domains
-- GRAIN: one row per workspace_id
--
-- OLDINGI MODELLAR (3 ta) → BITTA MODEL:
--   int_subscriptions_enriched  → MRR hisoblash
--   int_finance_aggregated      → workspace agregatsiya
--   int_payments_enriched       → payment failure kategoriya
--
-- MAS'ULIYAT:
--   Stripe ning 3 ta jadvalidan (subscriptions, invoices, payments)
--   workspace darajasida barcha billing metrikalarini hisoblaydi.
--   account_id bu yerda YO'Q — 3_integration da qo'shiladi.
-- =============================================================================

with subscriptions as (
    select
        workspace_id,
        customer_id,
        subscription_id,
        subscription_status,
        plan_id,
        unit_amount,
        seats_purchased,
        is_cancel_at_period_end,
        created_at,
        current_period_start_at,
        current_period_end_at,
        trial_end_at,

        -- MRR: unit_amount oylik narx (Stripe da asosan yillik bo'ladi)
        -- Agar unit_amount oylik bo'lsa: unit_amount * seats_purchased
        -- Agar yillik bo'lsa: unit_amount * seats_purchased / 12.0
        -- Loyihangizga qarab birini tanlang — hozir oylik deb olingan
        case
            when unit_amount > 0
            then unit_amount * seats_purchased
            else 0
        end                                             as mrr_amount,

        -- Oxirgi subscription (latest_status uchun)
        row_number() over (
            partition by workspace_id
            order by created_at desc
        )                                               as recency_rank

    from {{ ref('stg_stripe__subscriptions') }}
),

invoices as (
    select
        invoice_id,
        subscription_id,
        customer_id,
        invoice_status,
        amount_due,
        amount_paid,
        created_at
    from {{ ref('stg_stripe__invoices') }}
),

payments as (
    select
        p.payment_id,
        p.customer_id,
        p.invoice_id,
        p.payment_status,
        p.failure_code,
        p.amount,
        p.created_at,

        -- Failure kategoriya (oldin int_payments_enriched da edi)
        case
            when p.failure_code in (
                'card_declined', 'expired_card', 'card_velocity_exceeded')
                then 'card_issue'
            when p.failure_code in (
                'insufficient_funds', 'balance_insufficient')
                then 'funds_issue'
            when p.failure_code in (
                'fraudulent', 'issuer_declined', 'stolen_card', 'lost_card')
                then 'fraud_risk'
            when p.failure_code is not null
                then 'other'
            else null
        end                                             as failure_category,

        p.failure_code is not null                      as is_failed

    from {{ ref('stg_stripe__payments') }} p
),

-- Har customer uchun birinchi muvaffaqiyatli to'lov (trial → paid conversion)
first_payments as (
    select
        customer_id,
        min(created_at)                                 as first_payment_at,
        count(*)                                        as successful_payments_count
    from payments
    where payment_status = 'succeeded'
    group by 1
),

-- Haqiqiy foydalanilayotgan o'rinlar (Stripe quantity emas — internal DB dan)
user_seat_counts as (
    select
        internal_workspace_id                           as workspace_id,
        count(internal_user_id)                         as actual_seats_used
    from {{ ref('int_users_joined') }}
    group by 1
),

-- Eng og'ir payment failure (workspace darajasida)
payment_failures as (
    select
        i.subscription_id,
        s.workspace_id,
        -- Severity: fraud (4) > funds (3) > card (2) > other (1)
        case max(case
            when p.failure_category = 'fraud_risk'  then 4
            when p.failure_category = 'funds_issue' then 3
            when p.failure_category = 'card_issue'  then 2
            when p.failure_category = 'other'       then 1
            else 0
        end)
            when 4 then 'fraud_risk'
            when 3 then 'funds_issue'
            when 2 then 'card_issue'
            when 1 then 'other'
            else null
        end                                             as worst_failure_category
    from payments p
    left join invoices i     on p.invoice_id = i.invoice_id
    left join subscriptions s on i.subscription_id = s.subscription_id
    where p.is_failed = true
      and s.workspace_id is not null
    group by i.subscription_id, s.workspace_id
),

-- Workspace darajasida agregatsiya
workspace_billing as (
    select
        s.workspace_id,

        -- Customer ID (Stripe → internal ko'prik)
        max(s.customer_id)                              as customer_id,

        -- ── MRR sinyallari ──────────────────────────────────────────────
        sum(case when s.subscription_status = 'active'
            then s.mrr_amount else 0 end)               as active_mrr,
        sum(s.mrr_amount)                               as total_mrr,

        -- ── Subscription holati ─────────────────────────────────────────
        -- MAX(text) xatosi oldini olish: recency_rank = 1 → oxirgi yozuv
        max(case when s.recency_rank = 1
            then s.subscription_status end)             as latest_subscription_status,
        max(case when s.recency_rank = 1
            then s.plan_id end)                         as current_plan,
        max(case when s.recency_rank = 1
            then s.trial_end_at end)                    as trial_end_at,
        max(case when s.recency_rank = 1
            then s.current_period_end_at end)           as current_period_end_at,
        max(case when s.recency_rank = 1
            then s.current_period_start_at end)         as current_period_start_at,

        -- ── Churn sinyallari (3 tur) ────────────────────────────────────
        -- 1. Silent churn: to'lov o'tmadi, lekin hali bekor qilinmadi
        max(case when s.subscription_status = 'past_due'
            then 1 else 0 end)                          as is_payment_failing,
        -- 2. Intent churn: foydalanuvchi bekor qilishni boshladi
        max(case when s.is_cancel_at_period_end
            then 1 else 0 end)                          as is_churning_soon,

        -- ── Seat utilization ────────────────────────────────────────────
        sum(s.seats_purchased)                          as seats_purchased,

        -- ── Conversion ──────────────────────────────────────────────────
        max(fp.first_payment_at)                        as first_payment_at,
        max(fp.successful_payments_count)               as successful_payments_count,

        -- ── Expansion sinyallari (oldin fct_subscriptions da edi) ───────
        case
            when sum(s.seats_purchased) > 0
             and coalesce(max(uc.actual_seats_used), 0)::float
                 / nullif(sum(s.seats_purchased), 0) >= 0.9
            then true else false
        end                                             as is_upsell_candidate,
        case
            when sum(s.seats_purchased) > 1
             and coalesce(max(uc.actual_seats_used), 0)::float
                 / nullif(sum(s.seats_purchased), 0) < 0.3
            then true else false
        end                                             as is_downsell_risk,

        -- ── Trial at-risk sinyal (oldin fct_trial_conversion da edi) ────
        case
            when max(case when s.recency_rank = 1
                     then s.subscription_status end) = 'trialing'
             and max(case when s.recency_rank = 1
                     then s.trial_end_at end) is not null
             and datediff('day',
                 current_timestamp,
                 max(case when s.recency_rank = 1
                     then s.trial_end_at end)) between 0 and 3
             and max(fp.first_payment_at) is null
            then true else false
        end                                             as is_trial_at_risk

    from subscriptions s
    left join first_payments fp   on s.customer_id = fp.customer_id
    left join user_seat_counts uc on s.workspace_id = uc.workspace_id
    group by s.workspace_id
)

select
    wb.workspace_id,
    wb.customer_id,

    -- MRR
    wb.active_mrr,
    wb.total_mrr,

    -- Subscription holati
    wb.latest_subscription_status,
    wb.current_plan,
    wb.trial_end_at,
    wb.current_period_start_at,
    wb.current_period_end_at,

    -- Churn sinyallari
    wb.is_payment_failing,
    wb.is_churning_soon,

    -- Seat utilization
    wb.seats_purchased,
    coalesce(uc.actual_seats_used, 0)                   as seats_used,
    case
        when wb.seats_purchased > 0
        then coalesce(uc.actual_seats_used, 0)::float
             / nullif(wb.seats_purchased, 0)
        else 0
    end                                                 as seat_utilization_pct,

    -- Expansion sinyallari
    wb.is_upsell_candidate,
    wb.is_downsell_risk,

    -- Conversion
    wb.first_payment_at,
    wb.successful_payments_count,
    wb.is_trial_at_risk,

    -- Payment failure kategoriya
    pf.worst_failure_category                           as payment_failure_category

from workspace_billing wb
left join user_seat_counts uc on wb.workspace_id = uc.workspace_id
left join payment_failures pf on wb.workspace_id = pf.workspace_id
