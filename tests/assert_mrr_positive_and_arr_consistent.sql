-- tests/assert_mrr_positive_and_arr_consistent.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}
--
-- Objective: Validate two core financial business rules:
--   1. MRR should never be negative (signals a billing anomaly in Stripe)
--   2. ARR = MRR × 12 (internal consistency check with $1 tolerance for float rounding)
--
-- References: dim_accounts (int_accounts_scored → int_accounts_integrated)

select
    account_id,
    workspace_name,
    mrr,
    arr,
    case
        when mrr < 0
            then 'mrr_negative'
        when abs(arr - mrr * 12) > 1
            then 'arr_mrr_mismatch'
    end as failure_reason
from {{ ref('dim_accounts') }}
where mrr < 0
   or abs(arr - mrr * 12) > 1
