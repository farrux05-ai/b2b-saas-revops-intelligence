with master as (
    select * from {{ ref('int_accounts_integrated') }}
),

final as (
    select
        m.*,
        
        -- Health logic (Stage 3 Integration)
        case
            when m.latest_subscription_status = 'canceled' then 'Churned'
            when m.open_tickets > 5 then 'Support Critical'
            when m.last_activity_at < now() - interval '30 days' then 'Low Engagement'
            when m.open_deals_count > 0 and m.mrr > 0 then 'Expansion Target'
            else 'Healthy'
        end                                             as health_reason,
        
        case
            when m.latest_subscription_status = 'canceled' then 'Churned'
            when m.open_tickets > 5 or m.last_activity_at < now() - interval '30 days' then 'At Risk'
            else 'Healthy'
        end                                             as health_status,
        
        case 
            when m.latest_subscription_status != 'canceled' and (m.open_tickets > 5 or m.last_activity_at < now() - interval '30 days')
            then m.mrr
            else 0
        end                                             as mrr_at_risk

    from master m
)

select * from final
