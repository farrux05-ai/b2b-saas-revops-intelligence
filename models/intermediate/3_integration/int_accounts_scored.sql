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

health_reasons as (
    select
        *,
        -- Compute health_reason first
        case
            when latest_subscription_status = 'canceled'                          then 'Churned'
            when is_payment_failing = 1                                           then 'Payment Failing'
            when open_tickets > 5                                                 then 'Support Critical'
            when last_activity_at is null 
              or last_activity_at < current_timestamp - interval '30 days'        then 'Low Engagement'
            when open_deals_count > 0 and mrr > 0                                 then 'Expansion Target'
            else 'Healthy'
        end                                             as health_reason
    from master
),

final as (
    select
        r.*,
        
        -- Derive health_status directly from health_reason to prevent logical drift
        case
            when r.health_reason = 'Churned'                                        then 'Churned'
            when r.health_reason in ('Payment Failing', 'Support Critical', 'Low Engagement') then 'At Risk'
            else 'Healthy'
        end                                             as health_status,
        
        -- Derive mrr_at_risk directly from health_status
        case 
            when r.health_reason != 'Churned' 
             and r.health_reason in ('Payment Failing', 'Support Critical', 'Low Engagement')
            then r.mrr
            else 0
        end                                             as mrr_at_risk

    from health_reasons r
)

select * from final
