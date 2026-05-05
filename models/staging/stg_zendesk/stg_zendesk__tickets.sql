with source as (
    select * from {{ source('zendesk', 'tickets') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as ticket_id,
        cast(requester_email as varchar)                as requester_email,
        cast(assignee_id as varchar)                    as assignee_id,

        -- attributes
        cast(subject as varchar)                        as subject,
        cast(status as varchar)                         as ticket_status,
        cast(priority as varchar)                       as priority,

        -- satisfaction
        cast(satisfaction_rating as varchar)            as satisfaction_rating,
        cast(satisfaction_rating as varchar) = 'good'   as is_satisfied,
        cast(satisfaction_rating as varchar) = 'bad'    as is_unsatisfied,

        -- derived
        cast(status as varchar) in ('open', 'pending')  as is_open,
        cast(priority as varchar) in ('high', 'urgent') as is_high_priority,

        -- timestamps
        cast(created_at as timestamp)                   as created_at,
        cast(updated_at as timestamp)                   as updated_at,
        cast(solved_at as timestamp)                    as solved_at,

        -- resolution time in hours
        case
            when cast(solved_at as timestamp) is not null
            then date_diff(
                'hour',
                cast(created_at as timestamp),
                cast(solved_at as timestamp)
            )
        end                                             as resolution_hours,

        -- surrogate key
        {{ dbt_utils.generate_surrogate_key(['id']) }}  as ticket_sk

    from source
    qualify row_number() over (
        partition by id
        order by updated_at desc
    ) = 1
)

select * from renamed