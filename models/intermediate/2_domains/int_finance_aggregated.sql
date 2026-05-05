with subscriptions as (
    select * from {{ ref('stg_stripe__subscriptions') }}
),

spine as (
    select * from {{ ref('int_accounts_joined') }}
),

final as (
    select
        s.workspace_id,
        sp.account_id,
        sp.workspace_name,
        
        -- Revenue Math
        -- Distinguishing active MRR from total (potential) MRR
        sum(case when s.subscription_status = 'active' then s.mrr_amount else 0 end) as active_mrr,
        sum(s.mrr_amount)                                 as total_mrr,
        
        -- Expansion/Utilization Metrics
        sum(s.seats_used)                                 as seats_used,
        
        -- Silent Churn Signal (Payment Failure)
        -- Helps CS team to intervene before account drops off
        max(case when s.subscription_status = 'past_due' then 1 else 0 end) as is_payment_failing,
        
        max(s.subscription_status)                        as latest_subscription_status,
        max(s.plan_id)                                    as current_plan,
        
        case 
            when sum(s.mrr_amount) > 0 then 'paying'
            else 'non_paying'
        end                                             as payment_status

    from subscriptions s
    left join spine sp on s.workspace_id = sp.internal_workspace_id
    group by 1, 2, 3
)

select * from final
