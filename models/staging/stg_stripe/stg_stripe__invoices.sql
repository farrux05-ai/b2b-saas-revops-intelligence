with source as (
    select * from {{ source('stripe', 'invoices') }}
),

renamed as (
    select
        -- ids
        cast(id as varchar)                             as invoice_id,
        cast(subscription_id as varchar)                as subscription_id,
        cast(customer_id as varchar)                    as customer_id,

        -- attributes
        cast(status as varchar)                         as invoice_status,
        cast(billing_reason as varchar)                 as billing_reason,

        -- financials (cents → dollars)
        cast(amount_due as integer) / 100.0             as amount_due,
        cast(amount_paid as integer) / 100.0            as amount_paid,
        cast(amount_remaining as integer) / 100.0       as amount_remaining,

        -- timestamps
        cast(created as timestamp)                      as created_at,
        cast(due_date as timestamp)                     as due_date,
        cast(paid_at as timestamp)                      as paid_at,
        cast(period_start as timestamp)                 as period_start,
        cast(period_end as timestamp)                   as period_end,

        -- surrogate key
        {{ dbt_utils.generate_surrogate_key(['id']) }}  as invoice_sk

    from source
    qualify row_number() over (
        partition by id
        order by created desc
    ) = 1
)

select * from renamed