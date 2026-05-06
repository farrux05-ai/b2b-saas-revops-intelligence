{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_users_joined
-- LAYER: 1_identity
--
-- DESCRIPTION:
-- This model serves as the Global User Identity Spine. It resolves the "Human"
-- entity by stitching internal product users to their CRM representations (HubSpot).
-- 
-- BUSINESS LOGIC & L2A (Lead-to-Account) FALLBACK:
-- 1. Identity Anchor: Uses internal_user_id to ensure stability even if PII changes.
-- 2. Direct Match: Connects users to accounts via explicit workspace_id.
-- 3. Fuzzy Match (L2A): If an account isn't found via workspace, it attempts to
--    associate the user to an account via their business email domain, gracefully
--    handling "orphan leads" while explicitly excluding generic domains (e.g., gmail).
-- =============================================================================

-- 1. PRE-PROCESSING: Standardize strings and extract domains early for performance
with internal_users as (
    select
        user_id                                 as internal_user_id,
        workspace_id                            as internal_workspace_id,
        email,
        lower(email)                            as normalized_email,
        -- Extract domain for L2A matching
        split_part(lower(email), '@', 2)        as email_domain,
        user_role,
        created_at,
        activated_at,
        last_seen_at
    from {{ ref('stg_internal__users') }}
),

hubspot_contacts as (
    select
        hubspot_contact_id,
        hubspot_company_id, -- Original association in CRM
        lower(email)                            as normalized_email,
        first_name,
        last_name,
        job_title
    from {{ ref('stg_hubspot__contacts') }}
),

account_spine as (
    select
        account_id,
        internal_workspace_id,
        hubspot_company_id, -- Needed for Reverse ETL
        lower(domain)                           as account_domain
    from {{ ref('int_accounts_joined') }}
),

-- 2. DEFENSIVE FILTERING: Define generic domains to prevent false-positive Account matching
generic_domains as (
    select 'gmail.com' as domain union all
    select 'yahoo.com' union all
    select 'hotmail.com' union all
    select 'outlook.com' union all
    select 'icloud.com' union all
    select 'me.com' union all
    select 'aol.com'
),

-- 3. CORE LOGIC: Stitching users, accounts, and CRM data
user_account_stitching as (
    select
        u.internal_user_id,
        u.internal_workspace_id,
        u.email,
        u.user_role,
        u.created_at,
        u.activated_at,
        u.last_seen_at,
        h.hubspot_contact_id,
        h.hubspot_company_id as hubspot_company_id_raw, -- Original state in HubSpot
        h.first_name,
        h.last_name,
        h.job_title,
        
        -- IDENTITY RESOLUTION: Hierarchical Account Matching
        coalesce(
            s_direct.account_id,  -- Priority 1: Explicit DB Relationship
            s_domain.account_id   -- Priority 2: Inferred L2A Relationship
        ) as account_id,

        -- REVERSE ETL TARGET: Which HubSpot Company should this contact belong to?
        coalesce(
            s_direct.hubspot_company_id,
            s_domain.hubspot_company_id
        ) as hubspot_company_id_stitched,

        -- TRACEABILITY: Record how the association was made for downstream debugging
        case 
            when s_direct.account_id is not null then 'direct_match'
            when s_domain.account_id is not null then 'domain_match'
            else 'unmatched'
        end as match_method

    from internal_users u
    
    -- CRM STITCHING: Link to human attributes via normalized email
    left join hubspot_contacts h
        on u.normalized_email = h.normalized_email
        
    -- ACCOUNT MATCH 1 (Direct): Link via Product Workspace
    left join account_spine s_direct
        on u.internal_workspace_id = s_direct.internal_workspace_id
        
    -- FIX: Subquery avoidance for DuckDB compatibility in LEFT JOIN conditions
    left join generic_domains g
        on u.email_domain = g.domain

    -- ACCOUNT MATCH 2 (Fuzzy L2A): Link via Business Domain
    -- Applied ONLY if direct match fails AND domain is NOT generic
    left join account_spine s_domain
        on u.email_domain = s_domain.account_domain
        and s_direct.account_id is null 
        and g.domain is null -- Effectively: NOT IN generic_domains
),

-- 4. SURROGATE KEY GENERATION
final as (
    select
        -- Stable anchor independent of PII (emails)
        {{ dbt_utils.generate_surrogate_key(['internal_user_id']) }} as global_user_id,
        *,
        -- Logic for Reverse ETL: Is there a mismatch between HubSpot and our Truth?
        (hubspot_contact_id is not null 
         and hubspot_company_id_raw is null 
         and hubspot_company_id_stitched is not null) as is_l2a_orphan_fix_pending
    from user_account_stitching
)

select * from final