{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_product_aggregated
-- LAYER: 2_domains
-- GRAIN: one row per workspace_id
--
-- OLDINGI MODELLAR (2 ta) → BITTA MODEL:
--   int_usage_aggregated     → event agregatsiya, PQL signals
--   (fct_product_activation) → activation_rate, is_low_engagement (mart da edi)
--
-- MAS'ULIYAT:
--   PostHog events + int_users_joined dan user stats asosida
--   workspace darajasida barcha product metrikalarini hisoblaydi.
--   is_low_engagement bu yerda — fct_accounts_health dan ko'chirildi.
--   activation_rate bu yerda — fct_product_activation dan ko'chirildi.
-- =============================================================================

with events as (
    select * from {{ ref('stg_posthog__events') }}
),

-- int_users_joined: workspace darajasida user statistikasi
-- account_id ga group by qilinadi, keyin int_accounts_integrated da workspace bilan bog'lanadi
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

event_aggregation as (
    select
        workspace_id,

        -- Umumiy faollik
        count(event_id)                                 as total_product_events,
        max(occurred_at)                                as last_activity_at,

        -- ── Activation milestones ────────────────────────────────────────
        -- Loyihaga xos: StackFlow AI uchun Git + Sprint
        count(case when event_name = 'git_integration_connected'
            then 1 end) > 0                             as has_connected_git,
        count(case when event_name = 'sprint_started'
            then 1 end) > 0                             as has_started_sprint,
        count(case when event_name = 'ai_prioritization_used'
            then 1 end) > 0                             as has_used_ai_prioritization,

        -- ── PQL sinyal ──────────────────────────────────────────────────
        -- PQL = ikkita asosiy milestone bajarilgan
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

        -- ── Faollik ─────────────────────────────────────────────────────
        e.total_product_events,
        e.last_activity_at,

        -- ── Activation milestones ────────────────────────────────────────
        e.has_connected_git,
        e.has_started_sprint,
        e.has_used_ai_prioritization,
        e.is_pql,

        -- ── User statistikasi ────────────────────────────────────────────
        coalesce(us.total_users, 0)                     as total_users,
        coalesce(us.activated_users, 0)                 as activated_users,
        coalesce(us.active_users_last_30d, 0)           as active_users_last_30d,

        -- Activation rate (oldin fct_product_activation da edi)
        case
            when coalesce(us.total_users, 0) > 0
            then coalesce(us.activated_users, 0)::float
                 / us.total_users::float
            else 0
        end                                             as activation_rate,

        -- ── Engagement churn sinyal ──────────────────────────────────────
        -- NULL guard muhim: hech qachon ishlatmagan = eng katta xavf
        -- (oldin fct_accounts_health da CASE sifatida edi)
        case
            when e.last_activity_at is null
              or e.last_activity_at < current_timestamp - interval '30 days'
            then true else false
        end                                             as is_low_engagement

    from event_aggregation e
    left join user_stats us on e.workspace_id = us.workspace_id
)

select * from final
