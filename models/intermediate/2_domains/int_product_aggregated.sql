{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_product_aggregated
-- LAYER: 2_domains (Domain Aggregations)
-- GRAIN: One row per workspace_id
--
-- CONSOLIDATION RATIONALE:
--   Consolidates product engagement events and user activation metrics into a single
--   canonical workspace-level product domain model.
--
-- BUSINESS RESPONSIBILITY:
--   Aggregates PostHog product usage events alongside internal user lifecycle states
--   (from int_users_joined) at the workspace level.
--   Computes activation milestones (Git integration, Sprint start, AI prioritization),
--   Product Qualified Lead (PQL) status, workspace activation rate, and low-engagement
--   churn risk signals.
--
-- FIX (2026-08, audit): the final join used to be
--   `from event_aggregation e left join user_stats us ...`
-- which meant a workspace only appeared in this model AT ALL if it had at
-- least one PostHog event. Workspaces with real registered users but zero
-- product events (arguably the highest churn-risk group) were silently
-- dropped, which understated total_users/activation_rate downstream and
-- made the documented "last_activity_at is NULL -> severe churn risk" case
-- for is_low_engagement impossible to actually occur. We now drive the
-- grain from user_stats (every workspace that has users) and left join
-- event data onto it, so never-active workspaces correctly show up with
-- total_users > 0, total_product_events = 0, last_activity_at = NULL.
-- =============================================================================

with events as (
    select * from {{ ref('stg_posthog__events') }}
),

-- Workspace-level user lifecycle and activity statistics
user_stats as (
    select
        internal_workspace_id                           as workspace_id,
        count(internal_user_id)                         as total_users,
        count(case when is_activated
            then internal_user_id end)                  as activated_users,
        count(case when is_active_last_30d
            then internal_user_id end)                  as active_users_last_30d
    from {{ ref('int_users_joined') }}
    where internal_workspace_id is not null
    group by 1
),

-- Aggregate product events & activation milestones at the workspace grain
event_aggregation as (
    select
        workspace_id,

        -- Total event volume & recency
        count(event_id)                                 as total_product_events,
        max(occurred_at)                                as last_activity_at,

        -- ── Activation Milestones ──────────────────────────────────────
        -- StackFlow AI key product activation milestones
        count(case when event_name = 'git_integration_connected'
            then 1 end) > 0                             as has_connected_git,
        count(case when event_name = 'sprint_started'
            then 1 end) > 0                             as has_started_sprint,
        count(case when event_name = 'ai_prioritization_used'
            then 1 end) > 0                             as has_used_ai_prioritization,

        -- ── Product Qualified Lead (PQL) Signal ─────────────────────────
        -- PQL triggered when both primary activation milestones are completed
        (count(case when event_name = 'git_integration_connected'
             then 1 end) > 0
         and count(case when event_name = 'sprint_started'
             then 1 end) > 0)                           as is_pql

    from events
    where workspace_id is not null
    group by 1
),

final as (
    select
        us.workspace_id,

        -- ── Activity & Usage ───────────────────────────────────────────
        coalesce(e.total_product_events, 0)             as total_product_events,
        e.last_activity_at,

        -- ── Activation Milestones & PQL ────────────────────────────────
        coalesce(e.has_connected_git, false)            as has_connected_git,
        coalesce(e.has_started_sprint, false)           as has_started_sprint,
        coalesce(e.has_used_ai_prioritization, false)   as has_used_ai_prioritization,
        coalesce(e.is_pql, false)                       as is_pql,

        -- ── User Demographics & Adoption ───────────────────────────────
        us.total_users,
        us.activated_users,
        us.active_users_last_30d,

        -- Workspace activation rate (% of invited users who completed onboarding/activation)
        case
            when us.total_users > 0
            then us.activated_users::float
                 / us.total_users::float
            else 0
        end                                             as activation_rate,

        -- ── Low Engagement Churn Risk Signal ───────────────────────────
        -- Flagged true if inactive for 30+ days or never performed an event
        -- (never-active workspaces now genuinely reach this branch — see FIX above)
        -- FIX (2026-08): Anchored reference date to max event timestamp in dataset
        -- to prevent static/historical dataset drift where current_timestamp
        -- causes 100% of accounts to evaluate as low engagement.
        case
            when e.last_activity_at is null
              or e.last_activity_at < coalesce((select max(occurred_at) from events), current_timestamp) - interval '30 days'
            then true else false
        end                                             as is_low_engagement

    from user_stats us
    left join event_aggregation e on us.workspace_id = e.workspace_id
)

select * from final