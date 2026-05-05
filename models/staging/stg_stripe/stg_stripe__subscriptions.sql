{{ config(materialized='view') }}

with source as (
    select * from {{ source('stripe', 'subscriptions') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as subscription_id,
        cast(customer_id as varchar)                    as customer_id,
        cast(metadata__workspace_id as varchar)         as workspace_id,
        cast(metadata__hubspot_company_id as varchar)   as hubspot_company_id,

        -- attributes
        cast(status as varchar)                         as subscription_status,
        cast(plan_id as varchar)                        as plan_id,

        cast(unit_amount as integer)                    as unit_amount,
        cast(quantity as integer)                       as quantity,
        cast(quantity as integer)                       as seats_used,

        -- booleans
        cast(cancel_at_period_end as boolean)           as is_cancel_at_period_end,

        -- timestamps
        cast(created as timestamp)                      as created_at,
        cast(current_period_start as timestamp)         as current_period_start_at,
        cast(current_period_end as timestamp)           as current_period_end_at,
        cast(trial_end as timestamp)                    as trial_end_at

    from source
)

select * from renamed