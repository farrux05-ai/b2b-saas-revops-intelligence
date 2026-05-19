{{ config(materialized='table') }}

-- =============================================================================
-- int_accounts_integrated: Full Account 360 View
-- Layer: 3_integration
--
-- Materialized as TABLE because this is a heavily queried model by marts.
-- Joins all domain aggregations onto the account spine.
-- =============================================================================

with spine as (
    select * from {{ ref('int_accounts_joined') }}
),

workspaces as (
    select * from {{ ref('stg_internal__workspaces') }}
),

hubspot as (
    select * from {{ ref('stg_hubspot__companies') }}
),

sales as (
    select * from {{ ref('int_sales_aggregated') }}
),

finance as (
    select * from {{ ref('int_finance_aggregated') }}
),

support as (
    select * from {{ ref('int_support_aggregated') }}
),

usage as (
    select * from {{ ref('int_usage_aggregated') }}
),

icp as (
    select * from {{ ref('int_icp_scoring') }}
),

final as (
    select
        s.account_id,
        s.hubspot_company_id,
        s.internal_workspace_id,
        s.workspace_name,
        s.domain,
        
        -- Workspace info
        w.seat_limit,
        w.created_at,
        w.trial_started_at,
        w.trial_ended_at,
        w.converted_at,
        
        -- HubSpot info
        h.industry,
        h.company_name,
        h.utm_source,
        h.utm_campaign,
        
        -- Sales domain
        coalesce(sl.open_deals_count, 0)                 as open_deals_count,
        coalesce(sl.lifetime_revenue, 0)                as lifetime_revenue,
        sl.last_won_date,
        
        -- Finance domain
        coalesce(f.total_mrr, 0)                         as mrr,
        coalesce(f.active_mrr, 0)                        as active_mrr,
        f.latest_subscription_status,
        f.current_plan,
        f.is_payment_failing,
        f.is_churning_soon,
        
        -- Seat Utilization (Expansion blind spot)
        -- Solving the problem where Sales missed upsell opportunities
        coalesce(f.seats_purchased, 0)                   as seats_purchased,
        coalesce(f.seats_used, 0)                        as seats_used,
        case 
            when coalesce(f.seats_purchased, 0) > 0 
            then (coalesce(f.seats_used, 0)::float / f.seats_purchased::float) 
            else 0 
        end                                             as seat_utilization_pct,
        
        -- Expansion Signal
        case 
            when coalesce(f.seats_purchased, 0) > 0 
             and (coalesce(f.seats_used, 0)::float / f.seats_purchased::float) >= 0.9 
            then true 
            else false 
        end                                             as is_ready_for_upsell,
        
        -- Support domain
        coalesce(sp.total_tickets, 0)                   as total_tickets,
        coalesce(sp.open_tickets, 0)                    as open_tickets,
        coalesce(sp.high_priority_tickets, 0)           as high_priority_tickets,
        sp.avg_resolution_hours,
        sp.last_ticket_at,
        
        -- Usage domain
        coalesce(u.total_product_events, 0)             as total_product_events,
        u.last_activity_at,
        coalesce(u.is_pql, false)                       as is_pql,

        -- ICP Scoring & Segmentation (Layer 2)
        i.account_segment,
        i.icp_score,
        i.icp_tier

    from spine s
    left join workspaces w on s.internal_workspace_id = w.workspace_id
    left join hubspot h    on s.hubspot_company_id = h.hubspot_company_id
    left join sales sl     on s.hubspot_company_id = sl.hubspot_company_id
    left join finance f    on s.internal_workspace_id = f.workspace_id
    -- FIX #3: "Phantom Join" tuzatildi.
    -- Oldin: s.account_id = sp.account_id — lekin int_support_aggregated
    --        account_id ni int_users_joined → u.account_id dan oladi.
    --        int_accounts_joined dagi account_id boshqa surrogate key edi → doim NULL.
    -- Endi: ikkala tomon ham int_users_joined.account_id → int_accounts_joined.account_id
    --        bir xil surrogate key funksiyasidan kelgani uchun to'g'ri mos keladi.
    left join support sp   on s.account_id = sp.account_id
    left join usage u      on s.internal_workspace_id = u.workspace_id
    left join icp i        on s.account_id = i.account_id
)

select * from final
