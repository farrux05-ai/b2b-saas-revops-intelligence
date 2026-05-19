-- tests/assert_icp_score_in_valid_range.sql
{{ config(
    severity = 'error',
    store_failures = true
) }}

-- =============================================================================
-- Objective: Validate that ICP scores are mathematically correct.
--
-- Max possible score = 40 (industry) + 40 (segment) + 20 (revenue) = 100
-- Min possible score = 5 + 5 + 0 = 10 (fallback values)
--
-- Any account outside [0, 100] signals an error in int_icp_scoring logic
-- or a seed file with an unexpected value.
-- =============================================================================

select
    account_id,
    company_name,
    industry,
    account_segment,
    icp_score,
    icp_tier,
    case
        when icp_score < 0   then 'icp_score_negative'
        when icp_score > 100 then 'icp_score_above_max'
    end as violation_type
from {{ ref('int_icp_scoring') }}
where icp_score < 0
   or icp_score > 100
