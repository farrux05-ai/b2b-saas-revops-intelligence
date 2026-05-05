{{
    config(
        materialized='table',
        schema='marts'
    )
}}

with master as (
    select * from {{ ref('int_accounts_scored') }}
),

final as (
    select
        account_id,
        workspace_name,
        domain,
        industry,
        company_name as hubspot_company_name,
        
        -- Revenue & Expansion
        mrr,
        active_mrr,
        mrr * 12                                        as arr,
        account_segment,
        latest_subscription_status                      as subscription_status,
        current_plan,
        seat_limit,
        seats_used,
        seat_utilization_pct,
        is_ready_for_upsell,
        
        -- Health, Risk & Churn
        health_status,
        health_reason,
        mrr_at_risk,
        is_payment_failing,
        
        -- PLG & Product
        is_pql,
        total_product_events                            as product_events_count,
        last_activity_at,
        
        -- Aggregates
        total_tickets,
        open_tickets,
        open_deals_count,
        lifetime_revenue,
        
        -- Meta
        now()                                           as last_updated_at

    from master
)

select * from final
