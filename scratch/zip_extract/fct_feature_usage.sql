{{
    config(
        materialized='incremental',
        unique_key='usage_id',
        incremental_strategy='merge',
        on_schema_change='sync_all_columns'
    )
}}

-- =============================================================================
-- MODEL: fct_feature_usage
-- MART: product
-- GRAIN: one row per workspace × feature_category × week
--
-- AUDITORIYA: Product jamoasi — feature adoption, stickiness, upsell.
--
-- QOIDA: stg_posthog__events dan to'g'ri olish — ruxsat etilgan istisno.
--        Sabab: event-level raw data kerak (timestamp + event_name).
--        int_product_aggregated da already aggregated (workspace darajasida).
--        Bu mart feature_category × week darajasida aggregatsiya qiladi —
--        boshqa grain, shu sababli STG dan to'g'ri olish to'g'ri.
-- =============================================================================

with events as (
    select * from {{ ref('stg_posthog__events') }}
    {% if is_incremental() %}
    -- 3 kun overlap: late-arriving events uchun
    where occurred_at >= (
        select max(usage_week) - interval '3 days'
        from {{ this }}
    )
    {% endif %}
),

accounts as (
    select
        internal_workspace_id                           as workspace_id,
        account_id,
        account_segment
    from {{ ref('dim_accounts') }}
),

feature_categorization as (
    select
        event_id,
        workspace_id,
        event_name,
        occurred_at,
        case
            when event_name in (
                'project_created', 'task_completed')
                then 'Core Features'
            when event_name in (
                'git_integration_connected', 'api_key_generated',
                'ai_prioritization_used')
                then 'Advanced Features'
            when event_name in (
                'user_invited', 'role_changed')
                then 'Admin Features'
            else 'General Usage'
        end                                             as feature_category
    from events
    where workspace_id is not null
),

weekly_aggregation as (
    select
        workspace_id,
        feature_category,
        cast(date_trunc('week', occurred_at) as date)   as usage_week,
        count(distinct event_id)                        as total_events,
        count(distinct cast(date_trunc('day', occurred_at) as date))
                                                        as active_days
    from feature_categorization
    group by 1, 2, 3
)

select
    {{ dbt_utils.generate_surrogate_key([
        'u.workspace_id', 'u.feature_category', 'u.usage_week'
    ]) }}                                               as usage_id,
    a.account_id,
    u.workspace_id,
    u.feature_category,
    u.usage_week,
    u.total_events,
    u.active_days,
    a.account_segment

from weekly_aggregation u
left join accounts a on u.workspace_id = a.workspace_id
