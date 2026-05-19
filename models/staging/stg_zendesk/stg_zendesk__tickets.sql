{{ config(materialized='view') }}

with source as (
    select * from {{ source('zendesk', 'tickets') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as ticket_id,
        cast(requester_email as varchar)                as requester_email,
        lower(cast(requester_email as varchar))         as normalized_email,
        cast(assignee_id as varchar)                    as assignee_id,

        -- attributes
        cast(subject as varchar)                        as subject,
        cast(status as varchar)                         as ticket_status,
        cast(priority as varchar)                       as priority,

        -- timestamps
        cast(created_at as timestamp)                   as created_at,
        cast(updated_at as timestamp)                   as updated_at,
        cast(solved_at as timestamp)                    as solved_at

    from source
)

select * from renamed