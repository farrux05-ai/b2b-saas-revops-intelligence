with events as (
    select * from {{ ref('stg_posthog__events') }}
),

final as (
    select
        workspace_id,
        count(event_id)                                 as total_product_events,
        max(occurred_at)                                as last_activity_at,
        
        -- PQL (Product Qualified Lead) Signals
        -- Tracks specific activation milestones
        count(case when event_name = 'git_integration_connected' then 1 end) > 0 as has_connected_git,
        count(case when event_name = 'sprint_started' then 1 end) > 0 as has_started_sprint,
        
        -- Activation logic: connected git AND started a sprint
        -- This signal solves the "PLG Leakage" problem for Sales
        (count(case when event_name = 'git_integration_connected' then 1 end) > 0 and 
         count(case when event_name = 'sprint_started' then 1 end) > 0) as is_pql

    from events
    group by 1
)

select * from final
