{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_product_activation
-- MART: product
-- GRAIN: One row per workspace_id
--
-- TARGET AUDIENCE: Product & Growth Teams — Activation funnel, feature adoption, PLG signals.
--
-- BUSINESS CONTRACT:
--   Primary activation fact model. Sourced from int_product_aggregated and joined with dim_accounts.
-- =============================================================================

with usage as (
    select * from {{ ref('int_product_aggregated') }}
),

accounts as (
    select
        account_id,
        internal_workspace_id,
        workspace_name,
        domain,
        account_segment,
        mrr,
        current_plan,
        seats_purchased,
        seats_used,
        seat_utilization_pct,
        subscription_status,
        is_ready_for_upsell,
        seat_limit,
        workspace_created_at,
        trial_started_at,
        trial_ended_at,
        converted_at
    from {{ ref('dim_accounts') }}
),

-- User activation stats per workspace
user_stats as (
    select
        account_id,
        count(*)                                        as total_users,
        count(case when is_activated then 1 end)        as activated_users,
        count(case when is_active_last_30d then 1 end)  as active_users_last_30d
    from {{ ref('int_users_joined') }}
    group by 1
),

final as (
    select
        -- Workspace Identity & Foreign Keys
        a.internal_workspace_id                         as workspace_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,
        a.current_plan,

        -- Revenue Context
        a.mrr,
        a.subscription_status,

        -- User & Activation Metrics
        coalesce(us.total_users, 0)                     as total_users,
        coalesce(us.activated_users, 0)                 as activated_users,
        coalesce(us.active_users_last_30d, 0)           as active_users_last_30d,
        case
            when coalesce(us.total_users, 0) > 0
            then coalesce(us.activated_users, 0)::float
                / us.total_users::float
            else 0
        end                                             as activation_rate,

        -- Seat Utilization (Expansion Signal)
        a.seats_purchased,
        a.seats_used,
        a.seat_utilization_pct,
        a.is_ready_for_upsell,

        -- Product-Qualified Lead (PQL) & Telemetry Signals
        coalesce(u.is_pql, false)                       as is_pql,
        coalesce(u.has_connected_git, false)            as has_connected_git,
        coalesce(u.has_started_sprint, false)           as has_started_sprint,
        coalesce(u.total_product_events, 0)             as total_product_events,
        u.last_activity_at,

        -- Onboarding & Conversion Timestamps
        a.workspace_created_at,
        a.trial_started_at,
        a.trial_ended_at,
        a.converted_at,

        -- Conversion Flags
        a.converted_at is not null                      as is_converted,
        case
            when a.trial_ended_at is not null
             and a.trial_ended_at < current_timestamp
             and a.converted_at is null
            then true else false
        end                                             as is_trial_expired_no_convert

    from accounts a
    left join usage u
        on a.internal_workspace_id = u.workspace_id
    left join user_stats us
        on a.account_id = us.account_id
)

select * from final
