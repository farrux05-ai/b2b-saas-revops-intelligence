-- tests/assert_no_account_without_identity.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}

-- =============================================================================
-- Objective: Ensure every account in dim_accounts has at least one
--   valid identity anchor (internal workspace OR HubSpot company).
--
-- An account with BOTH NULL means the surrogate key was generated from
-- a NULL input → data corruption in int_accounts_joined.
-- =============================================================================

select
    account_id,
    hubspot_company_id,
    internal_workspace_id,
    workspace_name
from {{ ref('dim_accounts') }}
where hubspot_company_id is null
  and internal_workspace_id is null
