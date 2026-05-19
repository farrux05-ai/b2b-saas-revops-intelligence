{{ config(materialized='view') }}

with source as (
    select * from {{ source('internal', 'workspaces') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as workspace_id,
        cast(hubspot_company_id as varchar)             as hubspot_company_id,
        cast(stripe_customer_id as varchar)             as stripe_customer_id,

        -- attributes
        cast(name as varchar)                           as workspace_name,
        cast(plan as varchar)                           as plan,

        -- seat info
        cast(seat_limit as integer)                     as seat_limit,

        -- timestamps
        cast(created_at as timestamp)                   as created_at,
        cast(trial_started_at as timestamp)             as trial_started_at,
        cast(trial_ended_at as timestamp)               as trial_ended_at,
        cast(converted_at as timestamp)                 as converted_at

    from source
)

select * from renamed