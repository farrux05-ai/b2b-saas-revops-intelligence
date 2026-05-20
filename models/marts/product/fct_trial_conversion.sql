{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_trial_conversion
-- LAYER: Marts / Product
--
-- PURPOSE: Tracks Trial → Paid conversion funnel.
-- One row per trialing subscription. Shows which trials converted,
-- how long it took, and which ones are at risk of not converting.
--
-- KEY METRICS:
--   trial_conversion_rate = converted_trials / total_trials
--   avg_time_to_convert_days = avg days from trial_start to conversion
--   at_risk = trialing + trial expires within 3 days + no payment history
-- =============================================================================

with subscriptions as (
    select * from {{ ref('int_subscriptions_enriched') }}
),

-- Get payments per customer to identify conversion events
payments as (
    select
        customer_id,
        min(created_at)                             as first_successful_payment_at,
        count(*) filter (where payment_status = 'succeeded')
                                                    as successful_payments_count
    from {{ ref('int_payments_enriched') }}
    where payment_status = 'succeeded'
    group by 1
),

spine as (
    select
        account_id,
        internal_workspace_id,
        workspace_name,
        domain
    from {{ ref('int_accounts_joined') }}
),

trials as (
    -- All subscriptions that started as or are currently trialing
    select
        s.subscription_id,
        s.customer_id,
        s.workspace_id,
        sp.account_id,
        sp.workspace_name,
        sp.domain,

        s.plan_id,
        s.subscription_status,

        -- Trial window
        s.created_at                                    as trial_started_at,
        s.trial_end_at,
        s.current_period_start_at,
        s.current_period_end_at,

        -- Conversion: did this account ever make a successful payment?
        p.first_successful_payment_at                   as converted_at,
        coalesce(p.successful_payments_count, 0)        as successful_payments,

        -- Has converted = trial account with successful payment
        p.first_successful_payment_at is not null       as is_converted,

        -- Days from trial start to first payment (conversion velocity)
        case
            when p.first_successful_payment_at is not null
            then date_diff(
                'day',
                s.created_at,
                p.first_successful_payment_at
            )
        end                                             as time_to_convert_days,

        -- Trial days remaining
        case
            when s.trial_end_at is not null
            then date_diff('day', current_timestamp, s.trial_end_at)
        end                                             as trial_days_remaining,

        -- At-risk: trial expiring soon and not yet converted
        (
            s.subscription_status = 'trialing'
            and s.trial_end_at is not null
            and date_diff('day', current_timestamp, s.trial_end_at) <= 3
            and p.first_successful_payment_at is null
        )                                               as is_at_risk_of_expiring,

        -- Expired without converting
        (
            s.trial_end_at < current_timestamp
            and p.first_successful_payment_at is null
        )                                               as is_expired_unconverted

    from subscriptions s
    left join spine sp
        on s.workspace_id = sp.internal_workspace_id
    left join payments p
        on s.customer_id = p.customer_id
    -- Only trials: accounts that started in trial or currently trialing
    where s.subscription_status = 'trialing'
       or s.trial_end_at is not null
)

select * from trials
