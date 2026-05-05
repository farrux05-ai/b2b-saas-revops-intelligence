{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_arr_movements: Annual Recurring Revenue Movements
-- Mart: finance
--
-- Derived directly from fct_mrr_waterfall by scaling monthly revenue up to
-- annualized figures (MRR * 12).
-- =============================================================================

with mrr_movements as (
    select * from {{ ref('fct_mrr_waterfall') }}
),

arr_movements as (
    select
        -- Identifiers
        {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }} as arr_snapshot_id,
        account_id,
        month_date,

        -- Movement Classification
        mrr_movement_type                               as arr_movement_type,

        -- Financials (Annualized)
        previous_month_mrr * 12                         as previous_arr,
        mrr_change_amount * 12                          as arr_amount,
        mrr * 12                                        as current_arr

    from mrr_movements
)

select * from arr_movements
