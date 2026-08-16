{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_accounts_scored
-- LAYER: 3_integration (Multi-Signal Health Scoring)
-- GRAIN: One row per account_id
--
-- SCORING PRIORITY CASCADE (Strict Order):
--   1. Churned          : Subscription status is canceled.
--   2. Payment Failing  : Silent churn (past_due payment state).
--   3. Support Critical : High ticket burden (> 5 open support tickets).
--   4. Low Engagement   : Inactive in product (is_low_engagement flag from int_product_aggregated).
--   5. Expansion Target : Paying customer with open deals (upsell opportunity).
--   6. Healthy          : All health indicators normal.
--
-- BUSINESS RESPONSIBILITY:
--   Enriches int_accounts_integrated with health_reason, health_status, and mrr_at_risk.
--   Derives health_status and mrr_at_risk directly from health_reason to prevent logical drift.
--   Consumed downstream by dim_accounts in Marts.
-- =============================================================================

with master as (
    select * from {{ ref('int_accounts_integrated') }}
),

-- Step 1: Evaluate primary health_reason based on multi-domain risk cascade
health_reasons as (
    select
        *,
        case
            -- 1. Churned: Subscription has been canceled
            when latest_subscription_status = 'canceled'
                then 'Churned'

            -- 2. Payment Failing: Silent churn risk (past_due payment status)
            when is_payment_failing = 1
                then 'Payment Failing'

            -- 3. Support Critical: High support ticket volume indicates product/service friction
            when open_tickets > 5
                then 'Support Critical'

            -- 4. Low Engagement: Inactive product usage (is_low_engagement computed in int_product_aggregated)
            when is_low_engagement = true
                then 'Low Engagement'

            -- 5. Expansion Target: Active paying account with open pipeline deals
            when open_deals_count > 0
             and mrr > 0
                then 'Expansion Target'

            -- 6. Healthy: Normal operating state
            else 'Healthy'
        end                                             as health_reason

    from master
),

-- Step 2: Derive health_status & mrr_at_risk from health_reason to eliminate metric drift
final as (
    select
        r.*,

        -- High-level health status category for executive dashboards
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

        -- Financial exposure metric: MRR at risk due to churn drivers
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
