-- tests/assert_health_status_logic_consistent.sql
{{ config(
    severity = 'warn',
    store_failures = true
) }}

-- Objective: Ensure health_status logic is internally consistent
-- churned  → subscription_status = cancelled
-- at_risk  → past_due, urgent ticket, overdue invoice, or high open tickets/response
-- times
-- inactive → last_active_at > inactive_days_threshold
-- healthy  → no risk signals present

with
    health as (
        select
            account_key,
            account_name,
            health_status,
            subscription_status,
            overdue_invoices,
            urgent_support_tickets,
            last_active_at,
            avg_response_hours,
            total_support_tickets
        from {{ ref('int_customer_health_score') }}
    ),

    violations as (
        select
            account_key,
            account_name,
            health_status,
            'churned_but_not_cancelled' as violation_type
        from health
        where health_status = 'churned' and subscription_status != 'cancelled'

        union all

        select
            account_key,
            account_name,
            health_status,
            'healthy_but_has_risk' as violation_type
        from health
        where
            health_status = 'healthy'
            and (
                overdue_invoices > 0
                or urgent_support_tickets > 0
                or subscription_status = 'past_due'
                or avg_response_hours > {{ var("at_risk_response_hours") }}::numeric
                or (
                    last_active_at is not null
                    and last_active_at
                    < now()
                    - ({{ var("at_risk_days_since_active") }} * interval '1 day')
                )
            )

        union all

        select
            account_key,
            account_name,
            health_status,
            'inactive_but_recent_activity' as violation_type
        from health
        where
            health_status = 'inactive'
            and last_active_at
            >= now() - ({{ var("inactive_days_threshold") }} * interval '1 day')
    )

select *
from violations
