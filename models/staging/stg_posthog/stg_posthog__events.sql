with source as (
    select
        id,
        workspace_id,
        user_id,
        event_name,
        occurred_at
    from {{ source('internal', 'events') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as event_id,
        cast(workspace_id as varchar)                   as workspace_id,
        cast(user_id as varchar)                        as user_id,

        -- attributes
        cast(event_name as varchar)                     as event_name,

        -- timestamps
        cast(occurred_at as timestamp)                  as occurred_at

    from source
)

select * from renamed