-- tests/assert_seat_utilization_not_exceed_limit.sql
{{ config(
    severity = 'warn',
    store_failures = true
) }}

-- =============================================================================
-- Objective: seats_used should never exceed seat_limit.
--   If seats_used > seat_limit, it signals:
--   - An unenforced seat cap in the product (billing gap)
--   - A data pipeline issue where seat_limit was not propagated correctly
--
-- Severity: WARN (not ERROR) because the product may allow temporary overages.
-- =============================================================================

select
    account_id,
    workspace_name,
    seats_purchased,
    seats_used,
    seat_limit,
    seat_utilization_pct,
    'seats_used_exceeds_limit' as violation_type
from {{ ref('dim_accounts') }}
where seat_limit is not null
  and seats_used > seat_limit
