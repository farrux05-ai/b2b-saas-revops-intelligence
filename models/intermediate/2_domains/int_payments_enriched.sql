{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: int_payments_enriched
-- LAYER: 2_domains
-- SOURCE: stg_stripe__payments
--
-- PURPOSE: Payment-level enrichment with failure categorization.
-- This is the correct layer for failure_category business logic —
-- row-level classification belongs in Intermediate, NOT Staging.
--
-- CHURN SIGNAL: Payment failure categories are a leading indicator of churn:
--   - card_issue    → Update card reminder (Customer Success action)
--   - funds_issue   → Account health risk, flag for CS
--   - fraud_risk    → Immediate escalation required
--   - other         → Investigate manually
-- =============================================================================

with payments as (
    select * from {{ ref('stg_stripe__payments') }}
),

invoices as (
    select
        invoice_id,
        subscription_id
    from {{ ref('stg_stripe__invoices') }}
),

final as (
    select
        -- Identity
        p.payment_id,
        p.invoice_id,
        p.customer_id,
        i.subscription_id,

        -- Status
        p.payment_status,
        p.failure_code,

        -- =================================================================
        -- BUSINESS LOGIC: Payment Failure Categorization
        -- Used downstream for churn risk signals and CS alerting.
        -- Stripe failure codes: https://stripe.com/docs/error-codes
        -- =================================================================
        case
            when p.failure_code in ('card_declined', 'expired_card', 'card_velocity_exceeded')
                then 'card_issue'
            when p.failure_code in ('insufficient_funds', 'balance_insufficient')
                then 'funds_issue'
            when p.failure_code in ('fraudulent', 'issuer_declined', 'stolen_card', 'lost_card')
                then 'fraud_risk'
            when p.failure_code is not null
                then 'other'
            else null  -- Successful payments: no failure category
        end                                             as failure_category,

        -- Convenience flag: did this payment fail?
        p.failure_code is not null                      as is_failed,

        -- Financials
        p.amount,
        p.currency,

        -- Timestamps
        p.created_at

    from payments p
    left join invoices i using (invoice_id)
)

select * from final
