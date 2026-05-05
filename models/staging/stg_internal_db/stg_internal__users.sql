with source as (
    select * from {{ source('internal', 'users') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as user_id,
        cast(workspace_id as varchar)                   as workspace_id,

        -- attributes
        cast(email as varchar)                          as email,
        cast(role as varchar)                           as user_role,

        -- timestamps
        cast(created_at as timestamp)                   as created_at,
        cast(last_seen_at as timestamp)                 as last_seen_at,
        cast(invited_at as timestamp)                   as invited_at,
        cast(activated_at as timestamp)                 as activated_at,

        -- surrogate key
        {{ dbt_utils.generate_surrogate_key(['id']) }}  as user_sk

    from source
    qualify row_number() over (
        partition by id
        order by created_at desc
    ) = 1
)

select * from renamed