{{ config(materialized='view') }}

with source as (
    select * from {{ source('hubspot', 'engagements') }}
),

renamed as (
    select
        -- ids
        cast(hs_engagement_id as varchar)               as hubspot_engagement_id,
        cast(associated_company_id as varchar)          as hubspot_company_id,
        cast(owner_id as varchar)                       as owner_id,

        -- attributes
        cast(engagement_type as varchar)                as engagement_type,

        -- timestamps
        cast(created_at as timestamp)                   as created_at

    from source
)

select * from renamed
