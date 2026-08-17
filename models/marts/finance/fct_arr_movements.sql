{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_arr_movements
-- MART: finance
-- GRAIN: One row per account_id x month_date
--
-- TARGET AUDIENCE: Finance & Executive Leadership — Annualized ARR Movements (MRR * 12).
--
-- BUSINESS LOGIC:
--   Derived directly from fct_mrr_waterfall by scaling monthly MRR values to ARR (* 12).
-- =============================================================================

with mrr as (
    select * from {{ ref('fct_mrr_waterfall') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }}
                                                        as arr_snapshot_id,
    account_id,
    workspace_name,
    company_name,
    month_date,
    mrr_movement_type                                   as arr_movement_type,
    previous_month_mrr * 12                             as previous_arr,
    mrr_change_amount  * 12                             as arr_amount,
    mrr                * 12                             as current_arr

from mrr
