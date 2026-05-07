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

icp_data as (
    select * from {{ ref('int_icp_scoring') }}
),

pql_logic as (
    select
        a.workspace_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,
        
        -- ICP Fit (From our new model)
        i.icp_score,
        i.icp_tier,

        -- Milestone logic
        case
            when a.has_connected_git then 'Activated (Git Connected)'
            when a.has_started_sprint then 'Started (Sprint Started)'
            else 'Signed Up'
        end                                             as activation_milestone,

        -- Trial Context
        a.trial_started_at,
        a.trial_ended_at,
        case 
            when a.trial_ended_at is not null then date_diff('day', current_timestamp, a.trial_ended_at)
            else null
        end                                             as days_until_trial_expires,

        -- PQL Scoring (Internal Intent)
        a.total_product_events,
        a.is_pql,
        a.is_converted,
        
        -- Risk Signal
        case
            when a.is_converted = false 
             and a.trial_ended_at is not null 
             and date_diff('day', current_timestamp, a.trial_ended_at) < 3
             and a.total_product_events < 20
            then true else false
        end                                             as is_at_risk_of_not_converting

    from activation_data a
    left join icp_data i on a.account_id = i.account_id
    where a.is_converted = false -- Only focus on prospects/trialing accounts
),

scoring as (
    select
        *,
        -- PQL Intent Tiers
        case
            when total_product_events >= 50 and activation_milestone = 'Activated (Git Connected)' then 'HOT'
            when total_product_events >= 10 then 'WARM'
            else 'COLD'
        end                                             as intent_tier
    from pql_logic
),

final as (
    select
        *,
        -- GTM Priority Matrix (Intent x Fit)
        case
            when intent_tier = 'HOT' and icp_tier = 'High Fit' then '🔥 MUST WIN'
            when intent_tier = 'HOT' and icp_tier = 'Medium Fit' then '⚡ ACTIVE'
            when intent_tier = 'HOT' and icp_tier = 'Low Fit' then '🟠 NOTIFY'
            when intent_tier = 'WARM' and icp_tier = 'High Fit' then '🟢 HIGH POTENTIAL'
            when intent_tier = 'WARM' and icp_tier = 'Medium Fit' then '🔵 NURTURE'
            when icp_tier = 'Low Fit' then '⚪ MONITOR'
            else '🔘 INCUBATE'
        end                                             as gtm_priority,

        -- Recommended Action for Sales
        case
            when intent_tier = 'HOT' and icp_tier = 'High Fit' then 'Immediate Executive Outreach'
            when intent_tier = 'HOT' then 'Sales Qualification Call'
            when is_at_risk_of_not_converting and icp_tier != 'Low Fit' then 'High-Priority CS Recovery'
            when intent_tier = 'WARM' and icp_tier = 'High Fit' then 'Personalized Demo Invite'
            else 'Automated Nurture Sequence'
        end                                             as recommended_action

    from scoring
)

select * from final
