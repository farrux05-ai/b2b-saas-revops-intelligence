-- =============================================================================
-- fct_lead_funnel: Marketing Lead-to-Customer Conversion Funnel
-- Mart: marketing
--
-- Primary mart for the Marketing team. One row per HubSpot company.
-- Tracks the full journey: Lead → MQL → SQL → Opportunity → Customer.
-- Intended for: Funnel analysis, MQL quality, campaign attribution.
-- =============================================================================

with companies as (
    select * from {{ ref('stg_hubspot__companies') }}
),

accounts as (
    select
        hubspot_company_id,
        account_id,
        mrr,
        subscription_status,
        is_pql,
        product_events_count
    from {{ ref('dim_accounts') }}
),

final as (
    select
        -- Identity
        c.hubspot_company_id,
        a.account_id,
        c.company_name,
        c.domain,
        c.industry,
        c.employee_count,

        -- Funnel Position
        c.lifecycle_stage,
        c.lead_status,

        -- Conversion Flags
        c.lifecycle_stage = 'customer'                  as is_customer,
        c.lifecycle_stage in (
            'salesqualifiedlead', 'opportunity', 'customer'
        )                                               as is_sql_or_beyond,
        c.lifecycle_stage in (
            'marketingqualifiedlead', 'salesqualifiedlead',
            'opportunity', 'customer'
        )                                               as is_mql_or_beyond,

        -- PLG Overlay: did this lead convert via product usage?
        coalesce(a.is_pql, false)                       as is_pql,
        coalesce(a.product_events_count, 0)             as product_events_count,

        -- Revenue (only populated if they became a customer)
        coalesce(a.mrr, 0)                              as current_mrr,
        a.subscription_status,

        -- CRM Timestamps
        c.created_at                                    as became_lead_at,
        c.updated_at                                    as last_crm_activity_at,

        -- Lead Age: how long since this lead entered the funnel
        date_diff('day', cast(c.created_at as date), current_date)
                                                        as lead_age_days

    from companies c
    left join accounts a
        on c.hubspot_company_id = a.hubspot_company_id
)

select * from final
