{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_product_activation: Product Usage, Activation & PQL Signals
-- Mart: product
--
-- Primary mart for the Product team. One row per workspace.
-- Tracks activation milestones, feature adoption, and PLG conversion signals.
-- Intended for: Activation funnels, PQL scoring, onboarding optimization.
-- =============================================================================

with workspaces as (
    select * from {{ ref('stg_internal__workspaces') }}
),

usage as (
    select * from {{ ref('int_usage_aggregated') }}
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
        seat_limit,
        seats_used,
        seat_utilization_pct,
        subscription_status,
        is_ready_for_upsell
    from {{ ref('dim_accounts') }}
),

-- User activation stats per workspace
user_stats as (
    select
        account_id,
        count(*)                                        as total_users,
        count(*) filter (where is_activated)            as activated_users,
        count(*) filter (where is_active_last_30d)      as active_users_last_30d
    from {{ ref('dim_users') }}
    group by 1
),

final as (
    select
        -- Identity
        w.workspace_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,
        a.current_plan,

        -- Revenue Context
        a.mrr,
        a.subscription_status,

        -- User Metrics
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
        a.seat_limit,
        a.seats_used,
        a.seat_utilization_pct,
        a.is_ready_for_upsell,

        -- PQL & Feature Adoption Signals
        coalesce(u.is_pql, false)                       as is_pql,
        coalesce(u.has_connected_git, false)            as has_connected_git,
        coalesce(u.has_started_sprint, false)           as has_started_sprint,
        coalesce(u.total_product_events, 0)             as total_product_events,
        u.last_activity_at,

        -- Onboarding Timestamps
        w.created_at                                    as workspace_created_at,
        w.trial_started_at,
        w.trial_ended_at,
        w.converted_at,

        -- Conversion Flags
        w.converted_at is not null                      as is_converted,
        case
            when w.trial_ended_at is not null
             and w.trial_ended_at < current_timestamp
             and w.converted_at is null
            then true else false
        end                                             as is_trial_expired_no_convert

    from workspaces w
    left join accounts a
        on w.workspace_id = a.internal_workspace_id
    left join usage u
        on w.workspace_id = u.workspace_id
    left join user_stats us
        on a.account_id = us.account_id
)

select * from final
