with internal_users as (
    select * from {{ ref('stg_internal__users') }}
),

hubspot_contacts as (
    select * from {{ ref('stg_hubspot__contacts') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

stitching as (
    select
        u.user_id                                       as internal_user_id,
        u.workspace_id                                  as internal_workspace_id,
        s.account_id,
        u.email,
        u.user_role,
        h.hubspot_contact_id

    from internal_users u
    left join spine s
        on u.workspace_id = s.internal_workspace_id
    left join hubspot_contacts h
        on lower(u.email) = lower(h.email)
)

select
    {{ dbt_utils.generate_surrogate_key(['email']) }} as global_user_id,
    *
from stitching
