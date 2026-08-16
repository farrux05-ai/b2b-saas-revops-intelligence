{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: int_crm_aggregated
-- LAYER: 2_domains (Domain Aggregations)
-- GRAIN: One row per hubspot_company_id
--
-- CONSOLIDATION RATIONALE:
--   Consolidates CRM sales deal pipeline metrics and GTM activity engagements
--   into a single canonical company-level CRM domain model.
--
-- BUSINESS RESPONSIBILITY:
--   Aggregates HubSpot deals and engagements at the hubspot_company_id level.
--   Computes sales volume, deal stage distribution, lifetime revenue, pipeline velocity 
--   signals (stale deals > 90d, average sales cycle length, weighted pipeline value),
--   and engagement activity breakdowns (calls, emails, meetings).
-- =============================================================================

with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

engagements as (
    select * from {{ ref('stg_hubspot__engagements') }}
),

-- Aggregate sales deal pipeline metrics at the HubSpot company grain
deal_metrics as (
    select
        hubspot_company_id,

        -- Total deal creation volume
        count(hubspot_deal_id)                          as total_deals_created,

        -- Open pipeline deal count
        count(case
            when deal_stage not in ('closedwon', 'closedlost')
            then hubspot_deal_id end)                   as open_deals_count,

        -- Won deal count
        count(case
            when deal_stage = 'closedwon'
            then hubspot_deal_id end)                   as won_deals_count,

        -- Lost deal count
        count(case
            when deal_stage = 'closedlost'
            then hubspot_deal_id end)                   as lost_deals_count,

        -- Lifetime closed-won deal revenue
        coalesce(sum(case
            when deal_stage = 'closedwon'
            then amount else 0 end), 0)                 as lifetime_revenue,

        -- Most recent win date (used to flag dormant accounts)
        max(case
            when deal_stage = 'closedwon'
            then closed_at end)                         as last_won_date,

        -- ── Pipeline Velocity Signals ──────────────────────────────────
        -- Stale deals: Open deals created > 90 days ago without resolution
        count(case
            when deal_stage not in ('closedwon', 'closedlost')
             and datediff('day', created_at, current_timestamp) > 90
            then hubspot_deal_id end)                   as stale_deals_count,

        -- Average sales cycle length in days for won deals
        avg(case
            when deal_stage = 'closedwon'
             and closed_at is not null
             and closed_at > created_at
            then datediff('day', created_at, closed_at)
        end)                                            as avg_days_to_close_won,

        -- Probability-weighted pipeline value for active deals
        coalesce(sum(case
            when deal_stage not in ('closedwon', 'closedlost')
            then coalesce(amount, 0) * coalesce(probability, 0) / 100.0
            else 0 end), 0)                             as weighted_pipeline_value

    from deals
    where hubspot_company_id is not null
    group by 1
),

-- Aggregate GTM team engagement activities at the HubSpot company grain
engagement_metrics as (
    select
        hubspot_company_id,

        -- Total sales activity count
        count(hubspot_engagement_id)                    as total_activities,

        -- Activity volume by type
        count(case when engagement_type = 'CALL'
            then hubspot_engagement_id end)             as call_count,
        count(case when engagement_type = 'EMAIL'
            then hubspot_engagement_id end)             as email_count,
        count(case when engagement_type = 'MEETING'
            then hubspot_engagement_id end)             as meeting_count,

        -- Timestamp of most recent outreach / interaction
        max(created_at)                                 as last_engagement_at

    from engagements
    where hubspot_company_id is not null
    group by 1
)

-- FULL OUTER JOIN to retain companies with deals but no engagements, or vice versa
select
    coalesce(d.hubspot_company_id,
             e.hubspot_company_id)                      as hubspot_company_id,

    -- Deal & Pipeline Metrics
    coalesce(d.total_deals_created, 0)                  as total_deals_created,
    coalesce(d.open_deals_count, 0)                     as open_deals_count,
    coalesce(d.won_deals_count, 0)                      as won_deals_count,
    coalesce(d.lost_deals_count, 0)                     as lost_deals_count,
    coalesce(d.lifetime_revenue, 0)                     as lifetime_revenue,
    d.last_won_date,
    coalesce(d.stale_deals_count, 0)                    as stale_deals_count,
    d.avg_days_to_close_won,
    coalesce(d.weighted_pipeline_value, 0)              as weighted_pipeline_value,

    -- Engagement & Activity Metrics
    coalesce(e.total_activities, 0)                     as total_activities,
    coalesce(e.call_count, 0)                           as call_count,
    coalesce(e.email_count, 0)                          as email_count,
    coalesce(e.meeting_count, 0)                        as meeting_count,
    e.last_engagement_at

from deal_metrics d
full outer join engagement_metrics e
    on d.hubspot_company_id = e.hubspot_company_id
