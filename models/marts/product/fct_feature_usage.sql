-- =============================================================================
-- fct_feature_usage: Feature Adoption Heatmap
-- Mart: product
--
-- Aggregates product telemetry (PostHog) to track feature adoption across
-- workspaces. Helps identify stickiness and upsell opportunities.
-- =============================================================================

with events as (
    select * from {{ ref('stg_posthog__events') }}
),

accounts as (
    select * from {{ ref('dim_accounts') }}
),

feature_categorization as (
    select
        event_id,
        workspace_id,
        event_name,
        occurred_at as timestamp,
        case
            when event_name in ('project_created', 'task_completed') then 'Core Features'
            when event_name in ('git_integration_connected', 'api_key_generated') then 'Advanced Features'
            when event_name in ('user_invited', 'role_changed') then 'Admin Features'
            else 'General Usage'
        end as feature_category
    from events
),

usage_aggregation as (
    select
        workspace_id,
        feature_category,
        date_trunc('week', timestamp)::date             as usage_week,
        count(distinct event_id)                        as total_events,
        count(distinct date_trunc('day', timestamp))    as active_days
    from feature_categorization
    group by 1, 2, 3
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['u.workspace_id', 'u.feature_category', 'u.usage_week']) }} as usage_id,
        a.account_id,
        u.workspace_id,
        u.feature_category,
        u.usage_week,
        u.total_events,
        u.active_days,
        a.account_segment
    from usage_aggregation u
    left join accounts a 
        on u.workspace_id = a.internal_workspace_id
)

select * from final
