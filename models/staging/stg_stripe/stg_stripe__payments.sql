with source as (
    select * from {{ source('stripe', 'payments') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as payment_id,
        cast(invoice_id as varchar)                     as invoice_id,
        cast(customer_id as varchar)                    as customer_id,

        -- attributes
        cast(status as varchar)                         as payment_status,
        cast(failure_code as varchar)                   as failure_code,

        -- financials (cents → dollars)
        cast(amount as integer) / 100.0                 as amount,
        cast(currency as varchar)                       as currency,

        -- booleans
        cast(status as varchar) = 'failed'              as is_failed,

        -- timestamps
        cast(created as timestamp)                      as created_at,

        -- surrogate key
        {{ dbt_utils.generate_surrogate_key(['id']) }}  as payment_sk

    from source
    qualify row_number() over (
        partition by id
        order by created desc
    ) = 1
)

select * from renamed