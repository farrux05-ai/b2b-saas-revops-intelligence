{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: dim_users
-- MART: core
-- GRAIN: One row per global_user_id
--
-- BUSINESS CONTRACT:
--   Canonical User Dimension Model.
--   Applies PII masking & hashing at the Mart layer for data privacy compliance.
--   Raw email remains accessible in int_users_joined for identity resolution.
-- =============================================================================

with users as (
    select * from {{ ref('int_users_joined') }}
)

select
    -- Identity & Foreign Keys
    global_user_id,
    internal_user_id,
    account_id,

    -- PII Masking: Email (e.g. j***e@domain.com)
    regexp_replace(
        email,
        '^([^@]{1})[^@]*([^@]{1})@',
        '\1***\2@'
    )                                                   as email,

    -- PII Hashing: MD5 hash for downstream anonymous tracking
    md5(lower(trim(email)))                             as hashed_email,

    -- PII Masking: Name masking (e.g. John -> J***)
    case
        when first_name is not null
        then concat(substr(first_name, 1, 1), '***')
    end                                                 as first_name,
    case
        when last_name is not null
        then concat(substr(last_name, 1, 1), '***')
    end                                                 as last_name,

    -- User Profile Metadata
    job_title,
    user_role,
    hubspot_contact_id,
    match_method,

    -- User Activation & Activity Timestamps
    created_at,
    activated_at,
    last_seen_at,
    is_activated,
    is_active_last_30d,

    -- Audit Column
    current_timestamp                                   as last_updated_at

from users
