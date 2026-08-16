{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_arr_movements
-- MART: finance
-- GRAIN: one row per account_id × month_date
--
-- fct_mrr_waterfall dan derivatsiya — MRR × 12 = ARR.
-- O'ZGARISH yo'q — fct_mrr_waterfall dan oladi (u o'zgargan).
-- =============================================================================

with mrr as (
    select * from {{ ref('fct_mrr_waterfall') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }}
                                                        as arr_snapshot_id,
    account_id,
    month_date,
    mrr_movement_type                                   as arr_movement_type,
    previous_month_mrr * 12                             as previous_arr,
    mrr_change_amount  * 12                             as arr_amount,
    mrr                * 12                             as current_arr

from mrr
