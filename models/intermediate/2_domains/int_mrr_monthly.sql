{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_mrr_monthly
-- LAYER: 2_domains
-- GRAIN: One row per workspace_id x month_date
--
-- BUSINESS RESPONSIBILITY:
--   Reconstructs historical monthly recurring revenue (MRR) per workspace
--   from paid Stripe invoices and active subscriptions.
-- =============================================================================

with invoices as (
    select * from {{ ref('stg_stripe__invoices') }}
),

subscriptions as (
    select * from {{ ref('stg_stripe__subscriptions') }}
),

workspace_invoices as (
    select
        s.workspace_id,
        date_trunc('month', i.created_at)::date         as month_date,
        sum(i.amount_paid)                              as mrr,
        0                                               as at_risk_mrr
    from invoices i
    join subscriptions s on i.subscription_id = s.subscription_id
    where i.invoice_status = 'paid'
      and s.workspace_id is not null
    group by 1, 2
)

select * from workspace_invoices
