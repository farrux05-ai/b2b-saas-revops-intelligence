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
),

accounts as (
    select
        account_id,
        hubspot_company_id,
        workspace_name,
        company_name
    from {{ ref('dim_accounts') }}
)

select
    -- Identity & Foreign Keys
    e.hubspot_engagement_id                             as activity_id,
    e.hubspot_company_id,
    a.account_id,
    a.company_name,
    a.workspace_name,
    e.owner_id,

    -- Activity Dimensions
    e.engagement_type                                   as activity_type,

    -- Activity Timestamps
    e.created_at                                        as activity_at,
    cast(date_trunc('day', e.created_at) as date)       as activity_date

from engagements e
left join accounts a
    on e.hubspot_company_id = a.hubspot_company_id
where e.hubspot_company_id is not null
