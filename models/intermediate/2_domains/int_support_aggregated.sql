{{ config(materialized='view') }}

-- =============================================================================
-- int_support_aggregated: Support Health Metrics per Account
-- Layer: 2_domains
--
-- FIX: resolution_hours was removed from stg_zendesk__tickets (thin staging).
-- Resolution time computation now lives here — this is the correct layer
-- for derived business metrics.
-- =============================================================================

with tickets as (
    select * from {{ ref('stg_zendesk__tickets') }}
),

users as (
    select * from {{ ref('int_users_joined') }}
),

-- Compute resolution time in the domain layer (not staging)
tickets_with_resolution as (
    select
        *,
        -- Guard: only compute if solved, and solved_at is after created_at
        case
            when solved_at is not null
              and solved_at > created_at
            then date_diff('hour', created_at, solved_at)
        end                                             as resolution_hours
    from tickets
),

final as (
    select
        u.account_id,

        -- Volume metrics
        count(t.ticket_id)                              as total_tickets,

        -- Open tickets = active burden on CS team
        count(t.ticket_id) filter (
            where t.ticket_status in ('new', 'open', 'pending')
        )                                               as open_tickets,

        -- Escalation signal: urgent/high priority tickets
        count(t.ticket_id) filter (
            where t.priority in ('urgent', 'high')
        )                                               as high_priority_tickets,

        -- Avg resolution time in hours (quality of support metric)
        avg(t.resolution_hours)                         as avg_resolution_hours,

        -- Most recent ticket: staleness indicator
        max(t.created_at)                               as last_ticket_at

    from users u
    join tickets_with_resolution t
        on lower(u.email) = lower(t.requester_email)
    group by 1
)

select * from final
