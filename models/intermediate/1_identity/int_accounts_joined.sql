{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_accounts_joined
-- DESCRIPTION: Global Account Identity Spine for B2B SaaS.
-- This model consolidates identities from Product (Workspaces), Billing (Stripe),
-- and CRM (HubSpot) into a single unique Account Spine.
-- It also incorporates GTM Engineering enrichment (Clay/n8n).
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
        company_name,
        industry,
        -- GTM Enrichment fields
        annual_revenue,
        tech_stack,
        headquarter_city,
        headquarter_country,
        is_gtm_enriched
    from {{ ref('stg_hubspot__companies') }}
),

-- 1. ENRICHED PRODUCT ACCOUNTS
product_accounts as (
    select
        w.internal_workspace_id,
        w.hubspot_company_id,
        w.stripe_customer_id,
        coalesce(h.company_name, w.workspace_name)      as workspace_name,
        h.domain,
        h.industry,
        -- Enrichment attributes
        h.annual_revenue,
        h.tech_stack,
        h.headquarter_city,
        h.headquarter_country,
        h.is_gtm_enriched
    from workspaces w
    left join hubspot h on w.hubspot_company_id = h.hubspot_company_id
),

-- 2. CRM-ONLY LEADS (ANTI-JOIN PATTERN)
crm_only as (
    select
        null                                            as internal_workspace_id,
        h.hubspot_company_id,
        null                                            as stripe_customer_id,
        h.company_name                                  as workspace_name,
        h.domain,
        h.industry,
        -- Enrichment attributes
        h.annual_revenue,
        h.tech_stack,
        h.headquarter_city,
        h.headquarter_country,
        h.is_gtm_enriched
    from hubspot h
    left join workspaces w on h.hubspot_company_id = w.hubspot_company_id
    where w.hubspot_company_id is null 
),

-- 3. GLOBAL CONSOLIDATION
all_accounts as (
    select * from product_accounts
    union all
    select * from crm_only
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'coalesce(hubspot_company_id, internal_workspace_id)'
        ]) }}                                           as account_id,
        hubspot_company_id,
        internal_workspace_id,
        stripe_customer_id,
        workspace_name,
        domain,
        industry,
        annual_revenue,
        tech_stack,
        headquarter_city,
        headquarter_country,
        is_gtm_enriched
    from all_accounts
)

select * from final