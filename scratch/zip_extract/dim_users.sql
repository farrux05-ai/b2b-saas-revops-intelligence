{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: dim_users
-- MART: core
-- GRAIN: one row per global_user_id
--
-- QOIDA: PII masking FAQAT bu yerda — mart darajasida.
--        int_users_joined da email ochiq — bu mart uni yopadi.
--        Hisob-kitob yo'q, faqat masking va SELECT.
-- =============================================================================

with users as (
    select * from {{ ref('int_users_joined') }}
)

select
    -- ── Identity ──────────────────────────────────────────────────────────
    global_user_id,
    internal_user_id,
    account_id,

    -- ── PII Masking: Email (j***e@domain.com) ────────────────────────────
    regexp_replace(
        email,
        '^([^@]{1})[^@]*([^@]{1})@',
        '\1***\2@'
    )                                                   as email,

    -- ── PII Hashing: downstream identity stitching uchun ─────────────────
    md5(lower(trim(email)))                             as hashed_email,

    -- ── PII Masking: Ismlar (John → J***) ───────────────────────────────
    case
        when first_name is not null
        then concat(substr(first_name, 1, 1), '***')
    end                                                 as first_name,
    case
        when last_name is not null
        then concat(substr(last_name, 1, 1), '***')
    end                                                 as last_name,

    -- ── Profil ────────────────────────────────────────────────────────────
    job_title,
    user_role,
    hubspot_contact_id,
    match_method,

    -- ── Aktivatsiya ───────────────────────────────────────────────────────
    created_at,
    activated_at,
    last_seen_at,
    is_activated,
    is_active_last_30d,

    -- ── Audit ─────────────────────────────────────────────────────────────
    current_timestamp                                   as last_updated_at

from users
