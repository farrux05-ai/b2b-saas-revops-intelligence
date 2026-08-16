{{ config(materialized='view') }}

-- =============================================================================
-- MODEL: fct_pql_signals
-- MART: product
-- GRAIN: one row per workspace_id (faqat convert bo'lmaganlar)
--
-- AUDITORIYA: Sales + CS jamoasi — GTM priority matrix, outreach.
--
-- MANTIQ:
--   Intent (product faoliyati) × Fit (ICP) = GTM Priority
--   HOT  = git_connected + 50+ event
--   WARM = sprint_started + 10+ event
--   COLD = hech narsa yo'q
--
-- O'ZGARISH:
--   fct_product_activation dan keladi (int qatlamiga o'tilgan model).
--   int_icp_scoring to'g'ridan-to'g'ri ishlatiladi.
-- =============================================================================

with activation as (
    select * from {{ ref('fct_product_activation') }}
),

icp as (
    select
        account_id,
        icp_score,
        icp_tier
    from {{ ref('int_icp_scoring') }}
),

intent_scoring as (
    select
        a.workspace_id,
        a.account_id,
        a.workspace_name,
        a.domain,
        a.account_segment,
        a.workspace_created_at,
        a.trial_started_at,
        a.trial_ended_at,

        -- ICP
        i.icp_score,
        i.icp_tier,

        -- Activation milestone
        case
            when a.has_connected_git  then 'Activated (Git Connected)'
            when a.has_started_sprint then 'Started (Sprint Started)'
            else 'Signed Up'
        end                                             as activation_milestone,

        -- Trial qolgan kun
        case
            when a.trial_ended_at is not null
            then greatest(0, datediff('day', current_timestamp, a.trial_ended_at))
        end                                             as days_until_trial_expires,

        a.total_product_events,
        a.is_pql,
        a.is_converted,
        a.is_trial_at_risk                              as is_at_risk_of_not_converting,

        -- Intent tier (product faoliyati asosida)
        case
            when a.total_product_events >= 50
             and a.has_connected_git               then 'HOT'
            when a.total_product_events >= 10      then 'WARM'
            else 'COLD'
        end                                             as intent_tier

    from activation a
    left join icp i on a.account_id = i.account_id
    where a.is_converted = false  -- faqat prospektlar
),

final as (
    select
        *,

        -- GTM Priority Matrix (Intent × Fit)
        case
            when intent_tier = 'HOT'  and icp_tier = 'High Fit'   then 'MUST WIN'
            when intent_tier = 'HOT'  and icp_tier = 'Medium Fit' then 'ACTIVE'
            when intent_tier = 'HOT'  and icp_tier = 'Low Fit'    then 'NOTIFY'
            when intent_tier = 'WARM' and icp_tier = 'High Fit'   then 'HIGH POTENTIAL'
            when intent_tier = 'WARM' and icp_tier = 'Medium Fit' then 'NURTURE'
            when icp_tier = 'Low Fit'                              then 'MONITOR'
            else                                                        'INCUBATE'
        end                                             as gtm_priority,

        -- Raqamli tartib (BI sorting uchun)
        case
            when intent_tier = 'HOT'  and icp_tier = 'High Fit'   then 1
            when intent_tier = 'HOT'  and icp_tier = 'Medium Fit' then 2
            when intent_tier = 'HOT'  and icp_tier = 'Low Fit'    then 3
            when intent_tier = 'WARM' and icp_tier = 'High Fit'   then 4
            when intent_tier = 'WARM' and icp_tier = 'Medium Fit' then 5
            when icp_tier = 'Low Fit'                              then 6
            else                                                         7
        end                                             as gtm_priority_rank,

        -- Tavsiya etilgan harakat
        case
            when intent_tier = 'HOT' and icp_tier = 'High Fit'
                then 'Immediate Executive Outreach'
            when intent_tier = 'HOT'
                then 'Sales Qualification Call'
            when is_at_risk_of_not_converting and icp_tier != 'Low Fit'
                then 'High-Priority CS Recovery'
            when intent_tier = 'WARM' and icp_tier = 'High Fit'
                then 'Personalized Demo Invite'
            else
                'Automated Nurture Sequence'
        end                                             as recommended_action

    from intent_scoring
)

select * from final
