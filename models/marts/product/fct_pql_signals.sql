{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- =============================================================================
-- MODEL: fct_pql_signals
-- DESCRIPTION: Actionable PQL (Product Qualified Lead) Signals for Sales/CS.
-- This model identifies high-intent trial workspaces and recommends actions.
--
-- PQL Logic:
-- 1. HOT: Activated (Git connected) + > 50 events + Trial not expired.
-- 2. WARM: Started (Sprint started) + > 10 events + Trial not expired.
-- 3. COLD: Signed up but no significant activity.
-- =============================================================================

with activation_data as (
    select * from {{ ref('fct_product_activation') }}
),

pql_logic as (
    select
        workspace_id,
        account_id,
        workspace_name,
        domain,
        account_segment,
        
        -- Milestone logic
        case
            when has_connected_git then 'Activated (Git Connected)'
            when has_started_sprint then 'Started (Sprint Started)'
            else 'Signed Up'
        end                                             as activation_milestone,

        -- Lag Days: How long to reach the current milestone
        case
            when has_connected_git then date_diff('day', workspace_created_at, last_activity_at)
            else null
        end                                             as activation_lag_days,

        -- Trial Context
        trial_started_at,
        trial_ended_at,
        case 
            when trial_ended_at is not null then date_diff('day', current_timestamp, trial_ended_at)
            else null
        end                                             as days_until_trial_expires,

        -- PQL Scoring (Internal Intent)
        total_product_events,
        is_pql,
        is_converted,
        
        -- Risk Signal
        case
            when is_converted = false 
             and trial_ended_at is not null 
             and date_diff('day', current_timestamp, trial_ended_at) < 3
             and total_product_events < 20
            then true else false
        end                                             as is_at_risk_of_not_converting

    from activation_data
    where is_converted = false -- Only focus on prospects/trialing accounts
),

final as (
    select
        *,
        -- PQL Tiers
        case
            when total_product_events >= 50 and activation_milestone = 'Activated (Git Connected)' then '🔥 HOT'
            when total_product_events >= 10 then 'warm WARM'
            else '❄️ COLD'
        end                                             as pql_tier,

        -- Recommended Action for Sales
        case
            when total_product_events >= 50 and activation_milestone = 'Activated (Git Connected)' 
                then 'Immediate Outreach - High Intent'
            when is_at_risk_of_not_converting 
                then 'CS Intervention - Trial at Risk'
            when total_product_events >= 10 
                then 'Nurture - Send Best Practices'
            else 'Monitor - Early Stage'
        end                                             as recommended_action

    from pql_logic
)

select * from final
