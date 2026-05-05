-- tests/assert_mrr_positive_and_arr_consistent.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}
--
-- Objective: Validate two business rules:
--   1. MRR should never be negative (signals a billing anomaly)
--   2. ARR = MRR × 12 (consistency check)
--
-- Allows 1 dollar tolerance for ARR due to float rounding.

SELECT
    account_id,
    mrr,
    arr,
    CASE
        WHEN mrr < 0
            THEN 'mrr_negative'
        WHEN ABS(arr - mrr * 12) > 1
            THEN 'arr_mrr_mismatch'
    END AS failure_reason
FROM {{ ref('dim_accounts') }}
WHERE mrr < 0
   OR ABS(arr - mrr * 12) > 1
