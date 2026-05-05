with source as (
    select * from {{ source('hubspot', 'contacts') }}
),

renamed as (
    select
        -- ids
        cast(hs_object_id as varchar)                   as hubspot_contact_id,
        cast(associated_company_id as varchar)          as hubspot_company_id,

        -- attributes
        cast(firstname as varchar)                      as first_name,
        cast(lastname as varchar)                       as last_name,
        cast(firstname as varchar)
            || ' ' ||
        cast(lastname as varchar)                       as full_name,
        cast(email as varchar)                          as email,
        cast(jobtitle as varchar)                       as job_title,
        cast(hs_lead_status as varchar)                 as lead_status,

        -- timestamps
        cast(createdate as timestamp)                   as created_at,
        cast(lastmodifieddate as timestamp)             as updated_at,

        -- surrogate key
        {{ dbt_utils.generate_surrogate_key(['hs_object_id']) }}  as contact_sk

    from source
    qualify row_number() over (
        partition by hs_object_id
        order by lastmodifieddate desc
    ) = 1
)

select * from renamed