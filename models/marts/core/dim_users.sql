{{
    config(
        materialized='table',
        schema='marts'
    )
}}

select * from {{ ref('int_users_joined') }}
