with tickets as (
    select * from {{ ref('stg_zendesk__tickets') }}
),

users as (
    select * from {{ ref('int_users_joined') }}
),

final as (
    select
        u.account_id,
        count(t.ticket_id)                              as total_tickets,
        count(t.ticket_id) filter (
            where t.ticket_status in ('new', 'open', 'pending')
        )                                               as open_tickets,
        avg(t.resolution_hours)                         as avg_resolution_hours

    from users u
    join tickets t on lower(u.email) = lower(t.requester_email)
    group by 1
)

select * from final
