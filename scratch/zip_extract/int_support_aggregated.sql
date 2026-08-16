{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_support_aggregated
-- LAYER: 2_domains
-- GRAIN: one row per account_id
--
-- O'ZGARISH:
--   Oldin: int_users_joined ga to'g'ridan-to'g'ri JOIN → fan-out xavfi
--          (1 account × 5 user × 2 ticket = 10 emas 50 ticket chiqishi mumkin edi)
--   Endi:  email_to_account CTE DISTINCT bilan → har email bir account_id ga
--          map qilinadi, keyin ticket darajasida join qilinadi.
--
-- MAS'ULIYAT:
--   Zendesk ticketlarini email → account_id orqali boglab,
--   account darajasida support metrikalarini hisoblaydi.
-- =============================================================================

with tickets as (
    select * from {{ ref('stg_zendesk__tickets') }}
),

-- Fan-out oldini olish: bir email → bir account_id (DISTINCT)
-- int_users_joined da bir account ga ko'p user bo'lishi mumkin
email_to_account as (
    select distinct
        normalized_email,
        account_id
    from {{ ref('int_users_joined') }}
    where account_id is not null
      and normalized_email is not null
),

-- Resolution vaqtini hisoblash (oldin stg_zendesk da edi, to'g'ri joy: domain layer)
tickets_enriched as (
    select
        t.ticket_id,
        t.normalized_email,
        t.ticket_status,
        t.priority,
        t.created_at,
        t.solved_at,
        e.account_id,

        -- Guard: solved_at NULL bo'lishi yoki created_at dan oldin bo'lishi mumkin
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

        -- Hajm
        count(ticket_id)                                as total_tickets,

        -- Ochiq yuklamа (CS jamoasi uchun hozirgi holat)
        count(case
            when ticket_status in ('new', 'open', 'pending')
            then ticket_id end)                         as open_tickets,

        -- Eskalatsiya sinyal
        count(case
            when priority in ('urgent', 'high')
            then ticket_id end)                         as high_priority_tickets,

        -- Support sifati
        avg(resolution_hours)                           as avg_resolution_hours,

        -- Oxirgi murojaat
        max(created_at)                                 as last_ticket_at

    from tickets_enriched
    where account_id is not null
    group by 1
)

select * from final
