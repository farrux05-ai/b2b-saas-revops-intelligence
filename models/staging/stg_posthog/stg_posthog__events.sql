with source as (
    select * from {{ source('posthog', 'events') }}
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
        cast(occurred_at as timestamp)                  as occurred_at,

        -- surrogate key
        {{ dbt_utils.generate_surrogate_key(['id']) }}  as event_sk

    from source
    qualify row_number() over (
        partition by id
        order by occurred_at desc
    ) = 1
)

select * from renamed