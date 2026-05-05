{{ config(materialized='view') }}

-- =============================================================================
-- int_accounts_joined: Global Account Identity Spine
-- Layer: 1_identity
--
-- ARCHITECTURE NOTE:
-- stg_internal__workspaces is the PRIMARY spine because it already contains
-- all three foreign keys (hubspot_company_id, stripe_customer_id, workspace_id).
-- We only UNION in CRM-only accounts (HubSpot leads that have not signed up yet).
-- This eliminates the fragile UNION+GROUP BY MAX anti-pattern.
-- =============================================================================

with workspaces as (
    select
        workspace_id            as internal_workspace_id,
        hubspot_company_id,
        stripe_customer_id,
        workspace_name
    from {{ ref('stg_internal__workspaces') }}
),

hubspot as (
    select
        hubspot_company_id,
        domain,
        company_name
    from {{ ref('stg_hubspot__companies') }}
),

-- Accounts that exist in product (workspaces), enriched with HubSpot domain
product_accounts as (
    select
        w.internal_workspace_id,
        w.hubspot_company_id,
        w.stripe_customer_id,
        coalesce(w.workspace_name, h.company_name)      as workspace_name,
        h.domain
    from workspaces w
    left join hubspot h on w.hubspot_company_id = h.hubspot_company_id
),

-- CRM-only: HubSpot leads that have NOT yet signed up for the product
-- Prevents Leads from being invisible in the account spine
crm_only as (
    select
        null                                            as internal_workspace_id,
        h.hubspot_company_id,
        null                                            as stripe_customer_id,
        h.company_name                                  as workspace_name,
        h.domain
    from hubspot h
    left join workspaces w on h.hubspot_company_id = w.hubspot_company_id
    where w.hubspot_company_id is null  -- only leads without a workspace
),

all_accounts as (
    select * from product_accounts
    union all
    select * from crm_only
),

final as (
    select
        -- Surrogate key: prefer hubspot_company_id (stable CRM ID),
        -- fall back to internal workspace ID for orphan workspaces
        {{ dbt_utils.generate_surrogate_key([
            'coalesce(hubspot_company_id, internal_workspace_id)'
        ]) }}                                           as account_id,
        hubspot_company_id,
        internal_workspace_id,
        stripe_customer_id,
        workspace_name,
        domain
    from all_accounts
)

select * from final
