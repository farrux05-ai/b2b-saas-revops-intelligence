{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_trial_conversion
-- MART: product
-- GRAIN: One row per trialing subscription
--
-- TARGET AUDIENCE: Growth & Product Operations — Trial-to-Paid conversion funnel.
--
-- KEY METRICS:
--   - trial_conversion_rate = converted_trials / total_trials
--   - time_to_convert_days = days from trial start to first payment
--   - is_at_risk_of_expiring = trialing + expires within 3 days + no payment history
-- =============================================================================

with billing as (
    select * from {{ ref('int_billing_aggregated') }}
),

spine as (
    select
        account_id,
        internal_workspace_id,
        workspace_name,
        company_name,
        domain
    from {{ ref('dim_accounts') }}
),

trials as (
    select
        b.customer_id,
        b.workspace_id,
        sp.account_id,
        sp.workspace_name,
        sp.company_name,
        sp.domain,

        b.current_plan                                  as plan_id,
        b.latest_subscription_status                    as subscription_status,

        -- Trial Window
        b.current_period_start_at                       as trial_started_at,
        b.trial_end_at,
        b.current_period_start_at,
        b.current_period_end_at,

        -- Conversion Details
        b.first_payment_at                              as converted_at,
        coalesce(b.successful_payments_count, 0)        as successful_payments,
        b.first_payment_at is not null                  as is_converted,

        -- Conversion Velocity: Days to first payment
        case
            when b.first_payment_at is not null
            then datediff('day', b.current_period_start_at, b.first_payment_at)
        end                                             as time_to_convert_days,

        -- Trial Days Remaining
        case
            when b.trial_end_at is not null
            then datediff('day', current_timestamp, b.trial_end_at)
        end                                             as trial_days_remaining,

        coalesce(b.is_trial_at_risk, false)             as is_at_risk_of_expiring,

        -- Expired Without Converting
        (
            b.trial_end_at < current_timestamp
            and b.first_payment_at is null
        )                                               as is_expired_unconverted

    from billing b
    left join spine sp
        on b.workspace_id = sp.internal_workspace_id
    where b.latest_subscription_status = 'trialing'
       or b.trial_end_at is not null
)

select * from trials
