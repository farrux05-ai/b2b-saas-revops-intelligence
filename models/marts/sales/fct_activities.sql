-- =============================================================================
-- fct_activities: Sales Rep Activity Tracking
-- Mart: sales
--
-- Tracks activities (calls, emails, meetings) sourced directly from
-- HubSpot Engagements.
-- =============================================================================

with engagements as (
    select * from {{ ref('stg_hubspot__engagements') }}
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
