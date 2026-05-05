{{ config(materialized='view') }}

-- =============================================================================
-- int_users_joined: Global User Identity Stitching
-- Layer: 1_identity
--
-- Stitches internal product users to HubSpot contacts via email (case-insensitive).
-- global_user_id is based on internal_user_id (always present), NOT email,
-- because email can be NULL for users who haven't verified yet.
-- =============================================================================

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
        u.created_at,
        u.activated_at,
        u.last_seen_at,
        h.hubspot_contact_id,
        h.first_name,
        h.last_name,
        h.job_title

    from internal_users u
    left join spine s
        on u.workspace_id = s.internal_workspace_id
    left join hubspot_contacts h
        on lower(u.email) = lower(h.email)
)

select
    -- Use internal_user_id as SK anchor — email can be NULL
    {{ dbt_utils.generate_surrogate_key(['internal_user_id']) }} as global_user_id,
    *
from stitching
