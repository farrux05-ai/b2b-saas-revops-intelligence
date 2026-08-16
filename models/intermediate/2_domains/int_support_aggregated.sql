{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_support_aggregated
-- LAYER: 2_domains (Domain Aggregations)
-- GRAIN: One row per account_id
--
-- FAN-OUT PREVENTION IMPROVEMENT:
--   Instead of joining directly to int_users_joined (which has multiple users per account),
--   uses a DISTINCT email_to_account mapping to prevent artificial ticket count duplication.
--
-- BUSINESS RESPONSIBILITY:
--   Maps Zendesk support tickets to resolved account_id via normalized email.
--   Computes ticket resolution hours, open ticket load on Customer Success (CS),
--   high-priority escalations (urgent/high), average resolution time in hours, and ticket recency.
-- =============================================================================

with tickets as (
    select * from {{ ref('stg_zendesk__tickets') }}
),

-- Fan-out Protection: Extract unique email to account_id mapping to prevent user-level multiplication
email_to_account as (
    select distinct
        normalized_email,
        account_id
    from {{ ref('int_users_joined') }}
    where account_id is not null
      and normalized_email is not null
),

-- Enrich tickets with resolved account_id and compute resolution duration in hours
tickets_enriched as (
    select
        t.ticket_id,
        t.normalized_email,
        t.ticket_status,
        t.priority,
        t.created_at,
        t.solved_at,
        e.account_id,

        -- Resolution duration guard: compute only if solved and solved_at > created_at
        case
            when t.solved_at is not null
             and t.solved_at > t.created_at
            then datediff('hour', t.created_at, t.solved_at)
        end                                             as resolution_hours

    from tickets t
    left join email_to_account e
        on t.normalized_email = e.normalized_email
),

final as (
    select
        account_id,

        -- Total ticket volume
        count(ticket_id)                                as total_tickets,

        -- Active open ticket burden on CS team
        count(case
            when ticket_status in ('new', 'open', 'pending')
            then ticket_id end)                         as open_tickets,

        -- High-priority escalation signal
        count(case
            when priority in ('urgent', 'high')
            then ticket_id end)                         as high_priority_tickets,

        -- Average resolution time in hours (support quality metric)
        avg(resolution_hours)                           as avg_resolution_hours,

        -- Most recent ticket timestamp
        max(created_at)                                 as last_ticket_at

    from tickets_enriched
    where account_id is not null
    group by 1
)

select * from final
