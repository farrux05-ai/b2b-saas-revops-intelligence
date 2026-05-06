with source as (
    select * from {{ source('hubspot', 'companies') }}
),

renamed as (
    select
        -- ids
        cast(hs_object_id as varchar)                as hubspot_company_id,
        cast(domain as varchar)                      as domain,

        -- attributes
        cast(name as varchar)                        as company_name,
        cast(industry as varchar)                    as industry,
        cast(employee_count as integer)              as employee_count,
        cast(lifecyclestage as varchar)             as lifecycle_stage,
        cast(hs_lead_status as varchar)              as lead_status,
        cast(hubspot_owner_id as varchar)            as owner_id,
        cast(utm_source as varchar)                  as utm_source,
        cast(utm_campaign as varchar)                as utm_campaign,

        -- GTM Engineering / Clay Enrichment Fields
        cast(annual_revenue as varchar)              as annual_revenue,
        cast(tech_stack as varchar)                  as tech_stack,
        cast(city as varchar)                        as headquarter_city,
        cast(country as varchar)                     as headquarter_country,
        -- Tracking if this record was enriched via Clay/n8n
        cast(is_enriched as boolean)                 as is_gtm_enriched,

        -- timestamps
        cast(createdate as timestamp)                as created_at,
        cast(hs_lastmodifieddate as timestamp)       as updated_at

    from source
)

select * from renamed