with workspaces as (
    select 
        workspace_id as internal_workspace_id, 
        hubspot_company_id, 
        stripe_customer_id, 
        workspace_name
    from {{ ref('stg_internal__workspaces') }}
),

hubspot as (
    select 
        hubspot_company_id, 
        domain,
        company_name as workspace_name
    from {{ ref('stg_hubspot__companies') }}
),

stripe as (
    select distinct 
        customer_id as stripe_customer_id,
        hubspot_company_id,
        workspace_id as internal_workspace_id
    from {{ ref('stg_stripe__subscriptions') }}
),

-- Combine all potential identities to create a true global spine (UNION approach)
all_ids as (
    -- 1. All from Product (Workspaces)
    select hubspot_company_id, internal_workspace_id, stripe_customer_id, workspace_name from workspaces
    
    union
    
    -- 2. All from CRM (Leads/Companies not yet in product)
    select hubspot_company_id, null as internal_workspace_id, null as stripe_customer_id, workspace_name from hubspot
    
    union
    
    -- 3. All from Billing (Direct Stripe customers)
    select hubspot_company_id, internal_workspace_id, stripe_customer_id, null as workspace_name from stripe
),

-- Match domain from HubSpot for the global ID
spine_with_domain as (
    select 
        a.hubspot_company_id,
        a.internal_workspace_id,
        a.stripe_customer_id,
        a.workspace_name,
        h.domain
    from all_ids a
    left join hubspot h on a.hubspot_company_id = h.hubspot_company_id
),

final as (
    select 
        -- Global Surrogate Key based on domain or any available native ID
        {{ dbt_utils.generate_surrogate_key(['coalesce(domain, cast(hubspot_company_id as varchar), internal_workspace_id, stripe_customer_id)']) }} as account_id,
        max(hubspot_company_id)                                 as hubspot_company_id,
        max(internal_workspace_id)                              as internal_workspace_id,
        max(stripe_customer_id)                                 as stripe_customer_id,
        max(domain)                                             as domain,
        max(workspace_name)                                     as workspace_name

    from spine_with_domain
    group by 1
)

select * from final
