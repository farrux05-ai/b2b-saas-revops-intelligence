{{ config(materialized='view') }}

-- =============================================================================
-- int_accounts_scored: Multi-Signal Account Health Scoring
-- Layer: 3_integration
--
-- FIX: now() replaced with current_timestamp (portable across all SQL adapters).
-- FIX: is_payment_failing added to health scoring (was silently ignored before).
-- Scoring priority order: Churned > Payment Failing > Support Critical
--                       > Low Engagement > Expansion Target > Healthy
-- =============================================================================

with master as (
    select * from {{ ref('int_accounts_integrated') }}
),

final as (
    select
        m.*,
        
        -- Health logic (Stage 3 Integration)
        case
            when m.latest_subscription_status = 'canceled'                          then 'Churned'
            when m.is_payment_failing = 1                                           then 'Payment Failing'
            when m.open_tickets > 5                                                 then 'Support Critical'
            when m.last_activity_at is null 
              or m.last_activity_at < current_timestamp - interval '30 days'        then 'Low Engagement'
            when m.open_deals_count > 0 and m.mrr > 0                              then 'Expansion Target'
            else 'Healthy'
        end                                             as health_reason,
        
        case
            when m.latest_subscription_status = 'canceled'                          then 'Churned'
            when m.is_payment_failing = 1
              or m.open_tickets > 5
              or m.last_activity_at is null
              or m.last_activity_at < current_timestamp - interval '30 days'        then 'At Risk'
            else 'Healthy'
        end                                             as health_status,
        
        case 
            when m.latest_subscription_status != 'canceled'
              and (    m.is_payment_failing = 1
                   or m.open_tickets > 5
                   or m.last_activity_at is null
                   or m.last_activity_at < current_timestamp - interval '30 days')
            then m.mrr
            else 0
        end                                             as mrr_at_risk

    from master m
)

select * from final
