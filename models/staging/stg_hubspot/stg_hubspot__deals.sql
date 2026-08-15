with source as (
    select
        hs_object_id,
        associated_company_id,
        dealname,
        pipeline,
        dealstage,
        amount,
        hs_deal_stage_probability,
        createdate,
        closedate
    from {{ source('hubspot', 'deals') }}
),

renamed as (
    select
        -- ids
        cast(hs_object_id as varchar)                   as hubspot_deal_id,
        cast(associated_company_id as varchar)          as hubspot_company_id,

        -- attributes
        cast(dealname as varchar)                       as deal_name,
        cast(pipeline as varchar)                       as pipeline,
        cast(dealstage as varchar)                      as deal_stage,
        cast(amount as decimal(18, 2))                  as amount,
        cast(hs_deal_stage_probability as decimal(5, 2)) as probability,

        -- timestamps
        cast(createdate as timestamp)                   as created_at,
        cast(closedate as timestamp)                    as closed_at

    from source
)

select * from renamed