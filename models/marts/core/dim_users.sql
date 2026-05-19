-- =============================================================================
-- dim_users: Enriched User Directory
-- Mart: core
--
-- FIX: Replaced SELECT * anti-pattern with explicit column selection.
-- Internal/intermediate columns (internal_workspace_id, etc.) are excluded
-- from the mart to keep the BI surface clean.
-- =============================================================================

with users as (
    select * from {{ ref('int_users_joined') }}
),

final as (
    select
        -- Identity
        global_user_id,
        internal_user_id,
        account_id,
        email,

        -- Profile
        first_name,
        last_name,
        job_title,
        user_role,

        -- Linked CRM
        hubspot_contact_id,

        -- Activation Timestamps
        created_at,
        activated_at,
        last_seen_at,

        -- Derived activation status (30-day active window)
        activated_at is not null                        as is_activated,
        last_seen_at >= current_timestamp
            - interval '30 days'                        as is_active_last_30d

    from users
)

select * from final
