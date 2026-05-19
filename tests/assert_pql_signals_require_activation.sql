-- tests/assert_pql_signals_require_activation.sql
{{ config(
    severity = 'warn',
    store_failures = true
) }}

-- =============================================================================
-- Objective: A workspace flagged as PQL (Product Qualified Lead) should have
--   at least some product events. A PQL with zero product events is
--   contradictory and likely a data pipeline bug.
--
-- References: fct_pql_signals
-- =============================================================================

select
    workspace_id,
    account_id,
    total_product_events,
    is_pql,
    'pql_flagged_but_no_events' as violation_type
from {{ ref('fct_pql_signals') }}
where is_pql = true
  and total_product_events = 0
