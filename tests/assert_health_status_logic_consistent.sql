-- tests/assert_health_status_logic_consistent.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}

-- =============================================================================
-- Objective: Ensure health_status logic is internally consistent.
--
-- Rules (from int_accounts_scored):
--   Churned      → subscription_status = 'canceled'
--   At Risk      → is_payment_failing=1 OR open_tickets > 5 OR low engagement
--   Healthy      → none of the above risk signals
--
-- References: dim_accounts (materialized from int_accounts_scored)
-- =============================================================================

with accounts as (
    select
        account_id,
        workspace_name,
        health_status,
        health_reason,
        subscription_status,
        is_payment_failing,
        open_tickets,
        is_low_engagement,
        last_activity_at
    from {{ ref('dim_accounts') }}
),

violations as (
    -- Rule 1: If status=Churned, subscription must be 'canceled'
    select
        account_id,
        workspace_name,
        health_status,
        'churned_but_not_cancelled' as violation_type
    from accounts
    where health_status = 'Churned'
      and subscription_status != 'canceled'

    union all

    -- Rule 2: If status=Healthy, there should be no risk signals
    select
        account_id,
        workspace_name,
        health_status,
        'healthy_but_has_risk_signal' as violation_type
    from accounts
    where health_status = 'Healthy'
      and (
            is_payment_failing = 1
         or open_tickets > 5
         or is_low_engagement = true
      )

    union all

    -- Rule 3: If payment is failing, it should not be classified as Healthy
    select
        account_id,
        workspace_name,
        health_status,
        'payment_failing_but_healthy' as violation_type
    from accounts
    where is_payment_failing = 1
      and health_status = 'Healthy'
)

select * from violations
