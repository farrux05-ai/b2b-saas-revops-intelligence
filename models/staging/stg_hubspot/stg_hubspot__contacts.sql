with source as (
    select
        hs_object_id,
        associated_company_id,
        firstname,
        lastname,
        email,
        jobtitle,
        hs_lead_status,
        linkedin_url,
        is_enriched,
        createdate,
        lastmodifieddate
    from {{ source('hubspot', 'contacts') }}
),

renamed as (
    select
        -- ids
        cast(hs_object_id as varchar)                   as hubspot_contact_id,
        cast(associated_company_id as varchar)          as hubspot_company_id,

        -- attributes
        cast(firstname as varchar)                      as first_name,
        cast(lastname as varchar)                       as last_name,
        cast(email as varchar)                          as email,
        lower(trim(cast(email as varchar)))             as normalized_email,
        cast(jobtitle as varchar)                       as job_title,
        cast(hs_lead_status as varchar)                 as lead_status,

        -- GTM Engineering / Clay Enrichment Fields
        cast(linkedin_url as varchar)                   as linkedin_profile_url,
        cast(is_enriched as boolean)                    as is_gtm_enriched,

        -- timestamps
        cast(createdate as timestamp)                   as created_at,
        cast(lastmodifieddate as timestamp)             as updated_at

    from source
)

select * from renamed