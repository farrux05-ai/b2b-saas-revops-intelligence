{{ config(materialized='view') }}

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
        cast(activated_at as timestamp)                 as activated_at

    from source
)

select * from renamed