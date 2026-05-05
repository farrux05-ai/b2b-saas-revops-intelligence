{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- fct_activities: Sales Rep Activity Tracking
-- Mart: sales
--
-- Tracks activities (calls, emails, meetings). Since raw activity logs aren't
-- present in the mock data, this model simulates activity volume based on
-- contact creations and deal stage changes.
-- =============================================================================

with contacts as (
    select
        hubspot_contact_id                              as source_id,
        hubspot_company_id,
        'email_sent'                                    as activity_type,
        'Contact Created'                               as activity_description,
        created_at                                      as activity_at
    from {{ ref('stg_hubspot__contacts') }}
),

deals as (
    select
        hubspot_deal_id                                 as source_id,
        hubspot_company_id,
        'meeting_held'                                  as activity_type,
        'Deal Stage: ' || deal_stage                    as activity_description,
        coalesce(closed_at, created_at)                 as activity_at
    from {{ ref('stg_hubspot__deals') }}
),

all_activities as (
    select * from contacts
    union all
    select * from deals
),

final as (
    select
        -- Surrogate key for the activity
        {{ dbt_utils.generate_surrogate_key(['source_id', 'activity_type', 'activity_at']) }} as activity_id,
        
        -- Relationships
        a.hubspot_company_id,
        a.source_id,
        
        -- Dimensions
        a.activity_type,
        a.activity_description,
        
        -- Timestamps
        a.activity_at,
        date_trunc('day', a.activity_at)::date          as activity_date
        
    from all_activities a
    where a.hubspot_company_id is not null
)

select * from final
