-- =============================================================================
-- dim_users: Enriched User Directory (PII Protected)
-- Mart: core
--
-- One row per user. Links internal product users to HubSpot contacts and parent accounts.
-- PII PROTECTION: Email addresses are partially masked (e.g., j***e@domain.com) 
-- and names are masked to initials (e.g., J*** D***) for GDPR/CCPA compliance.
-- A secure deterministic MD5 hash (`hashed_email`) is provided for identity stitching.
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
        
        -- PII Masking: Mask email addresses (e.g., john.doe@company.com -> j***e@company.com)
        regexp_replace(email, '^([^@]{1})[^@]*([^@]{1})@', '\1***\2@') as email,
        
        -- PII Hashing: Secure deterministic MD5 hash for downstream cross-system stitching
        md5(lower(trim(email)))                         as hashed_email,

        -- PII Masking: Mask names to initials (e.g., John -> J***)
        case 
            when first_name is not null then concat(substr(first_name, 1, 1), '***')
            else null 
        end                                             as first_name,
        case 
            when last_name is not null then concat(substr(last_name, 1, 1), '***')
            else null 
        end                                             as last_name,
        
        -- Profile & Attributes
        job_title,
        user_role,

        -- Linked CRM
        hubspot_contact_id,

        -- Activation Timestamps
        created_at,
        activated_at,
        last_seen_at,

        -- Derived activation status (30-day active window)
        is_activated,
        is_active_last_30d

    from users
)

select * from final
