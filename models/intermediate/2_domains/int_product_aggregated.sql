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
        e.workspace_id,

        -- ── Activity & Usage ───────────────────────────────────────────
        e.total_product_events,
        e.last_activity_at,

        -- ── Activation Milestones & PQL ────────────────────────────────
        e.has_connected_git,
        e.has_started_sprint,
        e.has_used_ai_prioritization,
        e.is_pql,

        -- ── User Demographics & Adoption ───────────────────────────────
        coalesce(us.total_users, 0)                     as total_users,
        coalesce(us.activated_users, 0)                 as activated_users,
        coalesce(us.active_users_last_30d, 0)           as active_users_last_30d,

        -- Workspace activation rate (% of invited users who completed onboarding/activation)
        case
            when coalesce(us.total_users, 0) > 0
            then coalesce(us.activated_users, 0)::float
                 / us.total_users::float
            else 0
        end                                             as activation_rate,

        -- ── Low Engagement Churn Risk Signal ───────────────────────────
        -- Flagged true if inactive for 30+ days or never performed an event
        case
            when e.last_activity_at is null
              or e.last_activity_at < current_timestamp - interval '30 days'
            then true else false
        end                                             as is_low_engagement

    from event_aggregation e
    left join user_stats us on e.workspace_id = us.workspace_id
)

select * from final
