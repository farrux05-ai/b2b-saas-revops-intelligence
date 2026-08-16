{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_accounts_health
-- MART: customer_success
-- GRAIN: One row per paying account
--
-- TARGET AUDIENCE: Customer Success (CSM) Team — Churn prevention, QBRs, outreach.
--
-- BUSINESS LOGIC:
--   Selects directly from dim_accounts for paying accounts (subscription_status is not null).
--   Exposes pre-computed churn signals (is_payment_failing, is_churning_soon, is_low_engagement)
--   and health scores derived in intermediate layers.
-- =============================================================================

with accounts as (
    select * from {{ ref('dim_accounts') }}
)

select
    -- Identity & Segmentation
    account_id,
    domain,
    workspace_name,
    company_name,
    account_segment,
    current_plan,

    -- Financial Impact
    mrr,
    arr,
    mrr_at_risk,

    -- Health Status & Primary Cause
    health_status,
    health_reason,
    subscription_status,

    -- 3 Distinct Churn Risk Signals
    is_payment_failing,      -- 1. Silent Churn: Failed subscription payment
    is_churning_soon,        -- 2. Intent Churn: Scheduled cancellation
    is_low_engagement,       -- 3. Usage Churn: Inactive product telemetry

    -- Support Burden Context
    total_tickets,
    open_tickets,
    high_priority_tickets,
    avg_resolution_hours,
    last_ticket_at,

    -- Product Activity Context
    total_product_events,
    last_activity_at,
    is_pql,

    -- Expansion & Seat Utilization Signals
    seats_purchased,
    seats_used,
    seat_utilization_pct,
    is_ready_for_upsell

from accounts
-- CSM team focuses strictly on paying / active subscription accounts
where subscription_status is not null
