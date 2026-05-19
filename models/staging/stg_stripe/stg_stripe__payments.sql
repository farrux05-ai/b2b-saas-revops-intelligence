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

        -- timestamps
        cast(created as timestamp)                      as created_at

    from source
)

select * from renamed