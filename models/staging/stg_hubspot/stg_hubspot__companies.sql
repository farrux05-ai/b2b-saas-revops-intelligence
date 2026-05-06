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

        -- timestamps
        cast(createdate as timestamp)                as created_at,
        cast(hs_lastmodifieddate as timestamp)       as updated_at

    from source
)

select * from renamed