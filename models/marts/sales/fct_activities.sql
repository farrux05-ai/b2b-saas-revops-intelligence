{{
    config(
        materialized='incremental',
        unique_key='activity_id',
        incremental_strategy='merge',
        on_schema_change='sync_all_columns'
    )
}}

-- =============================================================================
-- MODEL: fct_activities
-- MART: sales
-- GRAIN: One row per hubspot_engagement_id
--
-- TARGET AUDIENCE: Sales Operations & Management — Rep activity & sales engagement.
--
-- ARCHITECTURAL RATIONALE:
--   Reads directly from stg_hubspot__engagements because row-level activity granularity
--   (individual timestamps, activity types, owner IDs) is required for sales rep productivity.
--   Aggregate activity metrics per account are maintained separately in int_crm_aggregated.
-- =============================================================================

with engagements as (
    select * from {{ ref('stg_hubspot__engagements') }}
    {% if is_incremental() %}
    -- 3-day overlap window for late-arriving records
    where created_at >= (
        select max(activity_at) - interval '3 day'
        from {{ this }}
    )
    {% endif %}
)

select
    -- Identity & Foreign Keys
    hubspot_engagement_id                               as activity_id,
    hubspot_company_id,
    owner_id,

    -- Activity Dimensions
    engagement_type                                     as activity_type,

    -- Activity Timestamps
    created_at                                          as activity_at,
    cast(date_trunc('day', created_at) as date)         as activity_date

from engagements
where hubspot_company_id is not null
