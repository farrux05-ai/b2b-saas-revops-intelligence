-- =============================================================================
-- fct_activities: Sales Rep Activity Tracking
-- Mart: sales
--
-- Tracks activities (calls, emails, meetings) sourced directly from
-- HubSpot Engagements.
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key='activity_id',
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

with engagements as (
    select * from {{ ref('stg_hubspot__engagements') }}
    {% if is_incremental() %}
    where created_at >= (select max(activity_at) - interval '3 days' from {{ this }})
    {% endif %}
),

final as (
    select
        hubspot_engagement_id                           as activity_id,
        
        -- Relationships
        hubspot_company_id,
        owner_id,
        
        -- Dimensions
        engagement_type                                 as activity_type,
        
        -- Timestamps
        created_at                                      as activity_at,
        date_trunc('day', created_at)::date             as activity_date
        
    from engagements
    where hubspot_company_id is not null
)

select * from final
